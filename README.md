# ecflow-openshift-agent

A python script to monitor ecflow jobs
* can create a job from a job template
* follows job progress
* prints log and other information
* can handle multiple instances running at the same time (in different oc namespaces)
* can be integrated to a python script or run as a command line tool


## Usage

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

### Example

Create a job in oc project myproject called myjob from template mytemplate. Template needs two arguments foo and baz which are provided. 

Agent will wait maximum 30 seconds for the job to finish (does not matter if it succeeds of fails). If job finishes before 30 seconds, agent will return with the return value of the job.

```
$ run-agent.py \
      --token-from-env-key oc_token \
      --api-server-url https://... \
      --project myproject \
      --command create-job-from-template \
      --template-name mytemplate \
      --override-job-name myjob \
      --job-param foo=bar \
      --job-param baz=bar \
      --job-timeout 30s
```

### Options
* `--log-level`: increase or decrease logging, value 1...5 (OPTIONAL)
* `--command`: specify command for agent, supported values:
  * create-job-from-template: creates a new job from an existing template in openshift
  * print-logs-for-job: prints the output of each container of a job
* `--token-from-env-key`: specify from which environment variable should a token be read. Note this is not the token itself, but the variable that holds the key
* `--api-server-url`: address of the openshift api (must include protocol)
* `--project`: openshift project (namespace)
* `--template-name`: when creating a job from template, specify which template to use
* `--override-job-name`: override the created job name with this (OPTIONAL)
* `--job-param`: specify a job template parameter, key=value (OPTIONAL)
* `--job-timeout`: specify timeout for the job, must include time unit for example 60s (OPTIONAL)
* `--job-name`: specify job name to print logs for (only when command=print-logs-for-job)
* `--log-container-name: specify which container logs to print, multiple names can be specified (OPTIONAL)
