from agent import Agent
import argparse
import logging
import sys

def string_to_log_level(log_level):
    if log_level == "critical":
        return logging.CRITICAL
    elif log_level == "error":
        return logging.ERROR
    elif log_level == "warning":
        return logging.WARNING
    elif log_level == "info":
        return logging.INFO
    elif log_level == "debug":
        return logging.DEBUG
    else:
        raise ValueError("Invalid log level: {}".format(log_level))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        help="log level: critical, error, warning, info, debug",
    )
    parser.add_argument(
        "--command",
        type=str,
        default="create_job_from_template",
        help="command: create_job_from_template",
    )
    parser.add_argument(
        "--token-from-env-key",
        type=str,
        required=True,
        default="ECFLOW_OPENSHIFT_TOKEN",
        help="token from env: ECFLOW_OPENSHIFT_TOKEN",
    )
    parser.add_argument(
        "--api-server-url",
        type=str,
        required=True,
        help="api server url: https://api.openshift.com",
    )
    parser.add_argument(
        "--project",
        type=str,
        required=True,
        help="openshift project (namespace)",
    )
    parser.add_argument(
        "--template-name",
        type=str,
        help="template name, when creating job from template",
    )
    parser.add_argument(
        "--override-job-name",
        type=str,
        default=None,
        help="override job name, when creating job from template",
    )
    parser.add_argument(
            "--job-param",
            type=str,
            action='append',
            default=[],
            help="job parameters, when creating job from template",
    )
    parser.add_argument(
            "--job-timeout",
            type=str,
            default="60s",
            help="job timeout, when creating job from template",
            )
    args = parser.parse_args()
    args.log_level = string_to_log_level(args.log_level)

    return args


args = parse_args()

agent = Agent(
    api_server_url=args.api_server_url,
    project=args.project,
    token_from_env_key=args.token_from_env_key,
    log_level=args.log_level,
)

if args.command == "create-job-from-template":
    assert args.template_name is not None, "template_name is required"

    params = {}
    for kv in args.job_param:
        k,v = kv.split('=')
        params[k] = v

    ret = agent.create_job_from_template(
        template_name=args.template_name,
        override_job_name=args.override_job_name,
        parameters=params,
        timeout=args.job_timeout,
    )

    if not ret:
        sys.exit(1)
else:
    print("Invalid command: {}".format(args.command))
    sys.exit(1)
