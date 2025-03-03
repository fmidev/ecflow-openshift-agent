import openshift as oc
import multiprocessing as mp
import os
import time
import logging
import datetime as dt
import tempfile

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-4s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _parse_time(t, mask="%Y-%m-%dT%H:%M:%SZ"):
    return dt.datetime.strptime(t, mask)


def _check_pod_status(job):
    unaccepted_reasons = (
        "ErrImagePull",
        "ImagePullBackOff",
        "CrashLoopBackOff",
    )
    wait_reasons = ("waiting", "terminated", "running")
    last_event = None
    time_since_last_event = None

    print_interval = 15
    job_start_time = job.model.status.startTime

    while True:
        sel = oc.selector("pod", labels={"job-name": job.model.metadata.name})
        pods = sel.objects()
        pods = [x for x in pods if x.model.status.startTime >= job_start_time]

        for pod in pods:
            for status in pod.model.status.containerStatuses:
                if status.phase == "Succeeded":
                    continue

                for w in wait_reasons:
                    if status.state[w].reason != oc.Missing:
                        wait_reason = status.state[w].reason

                if last_event != wait_reason:
                    last_event = wait_reason
                    time_since_last_event = time.time()
                    print_interval = 10

                if wait_reason in unaccepted_reasons:
                    logging.error(
                        f"Pod {pod.model.metadata.name} is not ready, waiting for {status.state.waiting.reason}"
                    )
                    return False

                diff = time.time() - time_since_last_event
                if wait_reason not in ("Completed") and diff > print_interval + 5:
                    print_interval += 10
                    logging.warning(
                        "pod {} has remained in state {} for {:.1f} seconds".format(
                            pod.model.metadata.name,
                            wait_reason,
                            time.time() - time_since_last_event,
                        )
                    )
        time.sleep(2)


def _wait_for_status(obj, status, timeout):
    r = oc.Result(f"wait-for-{status}")

    r.add_action(
        oc.oc_action(
            oc.cur_context(),
            "wait",
            cmd_args=[
                f"--timeout={timeout}",
                "--for=condition=" + status,
                obj.model.kind,
                obj.model.metadata.name,
            ],
        )
    )

    r.fail_if(f"Unable to check for {status}")


def canonical_name(name, max_len=63):
    name = (
        name.lower()
        .replace("_", "-")
        .replace(" ", "-")
        .replace(".", "-")
        .strip()
        .replace("/", "-")[0:max_len]
    )

    return name


def set_kubeconfig():
    try:
        os.mkdir("/tmp/oc-agent")
    except:
        pass

    tmpfile = tempfile.NamedTemporaryFile(dir="/tmp/oc-agent", mode='w+t', delete=False)
    os.environ['KUBECONFIG'] = tmpfile.name
    return tmpfile

class Agent:
    def __init__(
        self,
        api_server_url="https://api.ock.fmi.fi:6443",
        project="default",
        username=None,
        password=None,
        token=None,
        token_from_env_key=None,
        log_level=logging.INFO,
        no_login=False,
    ):
        self.project = project
        self.api_server_url = api_server_url
        self.kubeconfig = set_kubeconfig()

        if no_login:
            logging.info(f"Agent is run from within the OpenShift environment, so no login is required.")
            logging.info(f"Logged in as {oc.whoami()}")
            logging.info(f"Current project: {oc.get_project_name()}")
        else:
            with oc.api_server(self.api_server_url), oc.project(self.project):
                if username is not None and password is not None:
                    oc.login(username, password)
                else:
                    self.token = None
                    if token is not None:
                        self.token = token
                    elif token_from_env_key is not None:
                        self.token = os.environ[token_from_env_key]

                    assert (
                        self.token is not None
                    ), "No login credentials given, either username/password or token is required"

                    self.login_with_token(self.token)

            logging.info(f"Logged in as {oc.whoami()}")

            logged_project = oc.get_project_name()

            logging.info(f"Current project: {logged_project}")

            if logged_project == "default":
                logging.warning(
                    "Logged in to project default, possible problem with privileges"
                )

    def __del__(self):
        self.kubeconfig.close()
        try:
            os.unlink(self.kubeconfig.name)
        except:
            pass

    def login_with_token(self, token):
        assert token is not None, "No token given"

        r = oc.Result("login_with_token")

        r.add_action(
            oc.oc_action(oc.cur_context(), "login", cmd_args=["--token", token])
        )
        r.fail_if("Error when trying to login with token")

        logging.info(
            "Login to server {} succeeded with token ***".format(self.api_server_url)
        )
        return True

    def get_logs_for_job(self, job_name, container_name=None):
        def get_logs(pod_name, container_name):
            # Create a result for fetching logs
            log_result = oc.Result("get-logs")
            log_result.add_action(
                oc.oc_action(
                    oc.cur_context(),
                    "logs",
                    cmd_args=[pod_name, "-c", container_name, None],
                )
            )
            log_result.fail_if(f"Unable to get logs for pod {pod_name} container {container_name}")
            return log_result.out()

        if container_name is not None and type(container_name) == str:
            container_name = [container_name]

        r = oc.Result("get-job")
        r.add_action(
            oc.oc_action(
                oc.cur_context(),
                "get",
                cmd_args=["job", job_name, "-o", "json", None],
            )
        )
        r.fail_if(f"Unable to get job {job_name}")

        job = oc.APIObject(string_to_model=r.out().strip())
        job.model.metadata.namespace = ""

        label_selector = f"job-name={job.model.metadata.name}"

        pod_result = oc.Result("get-pods-for-job")
        pod_result.add_action(
            oc.oc_action(
                oc.cur_context(),
                "get",
                cmd_args=["pod", "-l", label_selector, "-o", "json", None],
            )
        )

        pod_result.fail_if(f"Unable to get pods for job {job.model.metadata.name}")

        pods_api_obj = oc.APIObject(string_to_model=pod_result.out().strip())

        if len(pods_api_obj.model["items"]) == 0:
            logging.error(f"No pods found for job {job_name}")
            return False, _

        logs = ""

        if container_name is None:
            # If user has not specified containers, list all
            container_name = [
                x["name"] for x in job.model.spec.template.spec.initContainers
            ]
            container_name += [x["name"] for x in job.model.spec.template.spec.containers]

        for req_name in container_name:
            found = False
            for pod in pods_api_obj.model["items"]:
                pod_name = pod["metadata"]["name"]

                all_containers = pod.spec.containers + pod.spec.initContainers

                for container in all_containers:
                    name = container["name"]
                    if req_name != name:
                        continue

                    found = True
                    logs += f"\npod: {pod_name} container: {name}\n"
                    logs += "-" * 80
                    logs += "\n" + get_logs(pod["metadata"]["name"], name)
                    logs += "-" * 80

                    break

            if not found:
                logging.error(f"Container {req_name} not found in any pod")
                return False, logs

        return True, logs


    def create_job_from_template(
        self,
        template_name,
        override_job_name=None,
        parameters={},
        run_async=False,
        delete_if_found=True,
        delete_after_finished=False,
        timeout="9999s",
        log_container_name=None,
    ):
        oc.tracking()
        if template_name.islower() == False:
            logging.warning("template_name should be lowercase")
            template_name = template_name.lower()

        r = oc.Result("get-template")
        r.add_action(
            oc.oc_action(
                oc.cur_context(),
                "get",
                cmd_args=["template", template_name, "-o", "json", None],
            )
        )
        r.fail_if(f"Unable to get template {template_name}")

        template = oc.APIObject(string_to_model=r.out().strip())
        template.model.metadata.namespace = ""

        # logging.debug(template.as_json())
        num_objects = len(template.model.objects)

        logging.info(f"Found {template.kind()} '{template.name()}' from server")

        processed_template = template.process(parameters=parameters)
        logging.info(f"Processed template with parameters: {parameters}")

        active_deadlines = [
            x.model.spec.template.spec.activeDeadlineSeconds for x in processed_template
        ]

        timeout_s = timeout
        if timeout_s[-1] == "s":
            timeout_s = int(timeout[:-1])

        for i, dl in enumerate(active_deadlines):
            if dl != oc.Missing and dl != timeout_s:
                logging.warning(
                    "job/{}: wait-timeout {}s does not match template timeout {}s".format(
                        processed_template[i].model.metadata.name, timeout_s, dl
                    )
                )

        job_name = [x.model.metadata.name for x in processed_template]

        if override_job_name is not None:
            if num_objects == 1 and type(override_job_name) != list:
                override_job_name = [canonical_name(override_job_name)]

            for i, job in enumerate(override_job_name):
                if job.islower() == False:
                    logging.warning("job_name should be lowercase")
                job_name[i] = canonical_name(job)
                processed_template[i].model.metadata.name = job_name[i]

        if delete_if_found is True:
            for i, o in enumerate(processed_template):
                logging.info(
                    f"Deleting existing {o.model.kind}/{o.model.metadata.name}"
                )
                self.delete_object(o.model.kind, o.model.metadata.name)

        obj_sel = oc.create(processed_template, cmd_args=None)

        assert len(obj_sel.objects()) > 0, "Failed to create any objects from template"

        for o in obj_sel.objects():
            logging.info("Created {}/{}".format(o.model.kind, o.model.metadata.name))

        if run_async is True:
            return

        ret = True
        for o in obj_sel.objects():
            ret = self.wait_until_finished(o, timeout, log_container_name)
            if not ret:
                ret = False

        return ret

    def delete_object(self, kind, name, timeout="15s"):
        r = oc.Result("delete-existing")
        r.add_action(
            oc.oc_action(
                oc.cur_context(),
                "delete",
                cmd_args=[
                    f"--timeout={timeout}",
                    "--ignore-not-found=true",
                    kind,
                    name,
                ],
            )
        )
        r.fail_if(f"Unable to delete {kind} {name}")

    def wait_until_finished(self, obj, timeout, log_container_name):
        def dump_failed_pod_information(pod):
            logging.error("{}".format(pod.describe()))

            for k, v in pod.logs().items():
                logging.error("{}".format(v.replace("\\n", "\n")))

        logging.info(
            "Waiting for {}/{} to be ready, timeout={}".format(
                obj.model.kind, obj.model.metadata.name, timeout
            )
        )

        return_value = False

        # timeout needs to be int from this point on
        timeout_s = timeout
        if timeout_s[-1] == "s":
            timeout_s = int(timeout[:-1])

        start = dt.datetime.now()
        last = dt.datetime.now()
        remaining_wait_time = dt.timedelta(seconds=timeout_s)

        job_found = False

        for i in range(5):
            # wait max 5 seconds for job to be created to openshift server
            o = oc.selector("{}/{}".format(obj.model.kind, obj.model.metadata.name))
            if o.count_existing() > 0:
                job_found = True
                break

            time.sleep(1)

        if job_found == False:
            logging.error("{}/{} not created to server after 5 seconds".format(obj.model.kind, obj.model.metadata.name))
            return False

        while True:
            time.sleep(1)

            if remaining_wait_time < dt.timedelta(seconds=0):
                logging.error("Timeout value {} reached".format(timeout))
                sel = oc.selector("pod", labels={"job-name": obj.model.metadata.name})

                for pod in sel.objects():
                    dump_failed_pod_information(pod)

                return False

            now = dt.datetime.now()
            if now - last > dt.timedelta(seconds=20):
                remaining_wait_time -= dt.timedelta(seconds=20)
                logging.info("Still waiting, {} remaining".format(remaining_wait_time))
                last = now

            try:
                o = oc.selector("{}/{}".format(obj.model.kind, obj.model.metadata.name))
                if o.count_existing() == 0:
                    logging.error("Did not find object {}/{}".format(obj.model.kind, obj.model.metadata.name))
                    return False
                o = o.object()
            except oc.OpenShiftPythonException as e:
                if "result" in e.as_dict():
                    result = e.as_dict()["result"].as_dict()
                    if result["actions"][0]["timeout"]:
                        logging.error("Timeout value {} reached".format(timeout))
                        sel = oc.selector(
                            "pod", labels={"job-name": obj.model.metadata.name}
                        )

                        for pod in sel.objects():
                            dump_failed_pod_information(pod)

                        return False
                raise e

            if o.model.status.succeeded == 1:
                return_value = True
                break
            if o.model.status.failed == 1:
                conds = o.model.status.conditions[0]
                logging.error(
                    "Job failed: {}, reason: {}".format(conds.message, conds.reason)
                )
                return_Value = False
                break

        if not return_value:
            job_start_time = obj.model.status.startTime
            sel = oc.selector("pod", labels={"job-name": obj.model.metadata.name})
            pods = sel.objects()
            pods = [x for x in pods if x.model.status.startTime >= job_start_time]

            logging.error(
                "Pods that failed: {}".format([x.model.metadata.name for x in pods])
            )
            for pod in pods:
                dump_failed_pod_information(pod)

        else:
            _, logs = self.get_logs_for_job(obj.model.metadata.name, log_container_name)
            logging.info(logs.replace("\\n", "\n"))

            compl = (
                _parse_time(obj.model.status.completionTime)
                if obj.model.status.completionTime != oc.Missing
                else None
            )
            start = (
                _parse_time(obj.model.status.startTime)
                if obj.model.status.startTime != oc.Missing
                else None
            )
            msg = f"{obj.model.kind} {obj.model.metadata.name} finished successfully"

            if compl is not None and start is not None:
                msg += " after {}".format(compl - start)

            logging.info(msg)

        return return_value
