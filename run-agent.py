#!/usr/bin/env python3
from ecflow_openshift_agent import Agent
import argparse
import logging
import sys
import os
import subprocess


def cleanup():
    try:
        os.remove(os.environ["KUBECONFIG"])
    except:
        pass


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
        default="create-job-from-template",
        help="command: create-job-from-template or print-logs-for-job",
    )
    parser.add_argument(
        "--no-login",
        action='store_true',
    )
    parser.add_argument(
        "--token-from-env-key",
        type=str,
        required=False if "--no-login" in sys.argv else True,
        default="ECFLOW_OPENSHIFT_TOKEN",
        help="token from env: ECFLOW_OPENSHIFT_TOKEN",
    )
    parser.add_argument(
        "--api-server-url",
        type=str,
        required=False if "--no-login" in sys.argv else True,
        help="api server url: https://api.openshift.com",
    )
    parser.add_argument(
        "--project",
        type=str,
        required=False if "--no-login" in sys.argv else True,
        help="openshift project (namespace)",
    )
    parser.add_argument(
        "--template-name",
        type=str,
        help="template name, when creating job from template",
    )
    parser.add_argument(
        "--job-name",
        type=str,
        help="job name, when getting logs from an existing job",
    )
    parser.add_argument(
        "--log-container-name",
        nargs="+",
        help="specify container name when getting logs (default: all containers)",
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
        action="append",
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
    no_login=args.no_login
)

return_code = None

if args.command == "create-job-from-template":
    assert args.template_name is not None, "template_name is required"

    params = {}
    for kv in args.job_param:
        k, v = kv.split("=", maxsplit=1)
        params[k] = v

    return_code = agent.create_job_from_template(
        template_name=args.template_name,
        override_job_name=args.override_job_name,
        parameters=params,
        timeout=args.job_timeout,
        log_container_name=args.log_container_name,
    )

elif args.command == "print-logs-for-job":
    assert args.job_name is not None, "job_name is required"
    return_code, logs = agent.get_logs_for_job(args.job_name, args.log_container_name)

    if return_code:
        print(logs.replace("\\n", "\n"))
else:
    print("Invalid command: {}".format(args.command))
    return_code = 1


cleanup()
sys.exit(return_code == False)
