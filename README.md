ecflow-openshift-agent

A python script to monitor ecflow jobs
* can create a job from a job template
* follows job progress
* prints log and other information
* can handle multiple instances running at the same time (in different oc namespaces)
* can be integrated to a python script or run as a command line tool


Usage:

```
$ run-agent.py
usage: run-agent.py [-h] [--log-level LOG_LEVEL] [--command COMMAND]
                    --token-from-env-key TOKEN_FROM_ENV_KEY --api-server-url
                    API_SERVER_URL --project PROJECT
                    [--template-name TEMPLATE_NAME]
                    [--override-job-name OVERRIDE_JOB_NAME]
                    [--job-param JOB_PARAM] [--job-timeout JOB_TIMEOUT]
run-agent.py: error: the following arguments are required: --token-from-env-key, --api-server-url, --project
```

Example:

```
$ run-agent.py \
      --token-from-env-key oc_token \
      --api-server-url https://... \
      --project myproject \
      --command create-job-from-template \
      --template-name mytemplate \
      --override-job-name mytemplate-bar \
      --job-param foo=bar \
      --job-timeout 30s
```
