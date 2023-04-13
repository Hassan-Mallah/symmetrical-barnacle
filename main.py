import argparse
import docker
import boto3
import time


def create_container(image, command):
    """ using image and command return docker container """
    client = docker.from_env()
    container = client.containers.run(
        image=image,
        command=command,
        detach=True,
        stdout=True,
        stderr=True
    )
    return container


def send_logs_to_cloudwatch(container, group_name, stream_name, credentials, region):
    """ read container logs and send them aws cloud watch """
    print("send_logs_to_cloudwatch")

    # create aws session
    session = boto3.Session(
        aws_access_key_id=credentials[0],
        aws_secret_access_key=credentials[1],
        region_name=region
    )

    logs_client = session.client('logs')

    # try to create logs group, else we already have one
    try:
        logs_client.create_log_group(logGroupName=group_name)
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass

    # try to create logs stream, else we already have one
    try:
        logs_client.create_log_stream(logGroupName=group_name, logStreamName=stream_name)
    except logs_client.exceptions.ResourceAlreadyExistsException:
        pass

    # store logs from container to send them to CloudWatch
    log_events = []

    # read logs stream from container and send them to CloudWatch
    for line in container.logs(stream=True):
        # save logs e.g. {'timestamp': 1681296784612, 'message': '20'}
        log_events.append({'timestamp': int(time.time() * 1000), 'message': line.decode('utf-8').strip()})
        print(log_events)

        # send every 1,000 logs to CloudWatch
        if len(log_events) == 1000:
            response = logs_client.put_log_events(
                logGroupName=group_name,
                logStreamName=stream_name,
                logEvents=log_events
            )
            log_events = []

    # in case of interruption, send rest of logs to CloudWatch
    if len(log_events) > 0:
        response = logs_client.put_log_events(
            logGroupName=group_name,
            logStreamName=stream_name,
            logEvents=log_events
        )


if __name__ == '__main__':
    # get args from command
    parser = argparse.ArgumentParser(description='Run a Docker container and send its logs to AWS CloudWatch.')
    parser.add_argument('--docker-image', type=str, required=True, help='The name of the Docker image to use.')
    parser.add_argument('--bash-command', type=str, required=True, help='The bash command to run inside the Docker container.')
    parser.add_argument('--aws-cloudwatch-group', type=str, required=True, help='The name of the AWS CloudWatch log group.')
    parser.add_argument('--aws-cloudwatch-stream', type=str, required=True, help='The name of the AWS CloudWatch log stream.')
    parser.add_argument('--aws-access-key-id', type=str, required=True, help='The AWS access key ID to use.')
    parser.add_argument('--aws-secret-access-key', type=str, required=True, help='The AWS secret access key to use.')
    parser.add_argument('--aws-region', type=str, required=True, help='The name of the AWS region to use.')

    args = parser.parse_args()

    # create docker container with image and bash command
    container = create_container(args.docker_image, args.bash_command)

    # send logs to AWS CloudWatch
    send_logs_to_cloudwatch(container, args.aws_cloudwatch_group, args.aws_cloudwatch_stream, (args.aws_access_key_id,
                            args.aws_secret_access_key), args.aws_region)
