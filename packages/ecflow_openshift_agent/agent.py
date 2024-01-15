import openshift as oc
import multiprocessing as mp
import os
import time
import logging
import datetime as dt

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
    ):
        self.project = project
        self.api_server_url = api_server_url

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

    def create_job_from_template(
        self,
        template_name,
        override_job_name=None,
        parameters={},
        run_async=False,
        delete_if_found=True,
        delete_after_finished=False,
        timeout="9999s",
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

        logging.debug(template.as_json())
        num_objects = len(template.model.objects)

        logging.info(f"Found {template.kind()} '{template.name()}' from server")
        logging.info(f"Given template parameters are: {parameters}")

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
            ret = self.wait_until_finished(o, timeout)
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

    def wait_until_finished(self, obj, timeout):
        logging.info(
            "Waiting for {}/{} to be ready, timeout={}".format(
                obj.model.kind, obj.model.metadata.name, timeout
            )
        )

        return_value = False

        # oc.tracking()

        # timeout needs to be int from this point on
        timeout_s = timeout
        if timeout_s[-1] == "s":
            timeout_s = int(timeout[:-1])
        with oc.timeout(timeout_s):

            last = dt.datetime.now()
            wait_time = dt.timedelta(seconds=timeout_s)

            while True:
                try:
                    obj = oc.selector(
                        "{}/{}".format(obj.model.kind, obj.model.metadata.name)
                    ).object()
                except oc.OpenShiftPythonException as e:
                    result = e.as_dict()["result"].as_dict()
                    if result["actions"][0]["timeout"]:
                        logging.error("Timeout value {} reached".format(timeout))
                        return False
                    raise e

                if obj.model.status.succeeded == 1:
                    return_value = True
                    break
                if obj.model.status.failed == 1:
                    conds = obj.model.status.conditions[0]
                    logging.error(
                        "Job failed: {}, reason: {}".format(conds.message, conds.reason)
                    )
                    return_Value = False
                    break

                time.sleep(1)

                now = dt.datetime.now()
                if now - last > dt.timedelta(seconds=20):
                    wait_time -= dt.timedelta(seconds=20)
                    logging.info("Still waiting, {} remaining".format(wait_time))
                    last = now

        if not return_value:
            job_start_time = obj.model.status.startTime
            sel = oc.selector("pod", labels={"job-name": obj.model.metadata.name})
            pods = sel.objects()
            pods = [x for x in pods if x.model.status.startTime >= job_start_time]

            logging.error(
                "Pods that failed: {}".format([x.model.metadata.name for x in pods])
            )
            for pod in pods:
                logging.error(
                    "Pod {} description: {}".format(
                        pod.model.metadata.name, pod.describe()
                    )
                )

                for k, v in pod.logs().items():
                    logging.error(
                        "Pod {} logs: {}".format(
                            pod.model.metadata.name, v.replace("\\n", "\n")
                        )
                )

        else:
            obj = oc.selector(
                "{}/{}".format(obj.model.kind, obj.model.metadata.name)
            ).object()

            sel = oc.selector("pod", labels={"job-name": obj.model.metadata.name})

            for pod in sel.objects():
                for k, v in pod.logs().items():
                    logging.info(v.replace("\\n", "\n"))

            logging.info(
                "Job {} finished successfully after {}".format(
                    obj.model.metadata.name,
                    _parse_time(obj.model.status.completionTime)
                    - _parse_time(obj.model.status.startTime),
                )
            )

        return return_value
