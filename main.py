import re
import sys
import time

import boto3
import argparse
from botocore import exceptions as scrum  # :)


def get_fs_info(ssm, instanceId: str):
    print("Obtaining filesystem info...")
    while True:
        response = ssm.send_command(
            InstanceIds=[instanceId],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": ["lsblk -oMOUNTPOINT,PKNAME,NAME,FSTYPE -rn | grep '/ '| awk '{print $2,$3,$4}'"]},
        )
        time.sleep(10)
        inv = ssm.get_command_invocation(CommandId=response["Command"]["CommandId"],
                                         InstanceId=instanceId)
        if inv["Status"] == "Success":
            fsInfo = inv["StandardOutputContent"].split()
            if not re.search("\Anvme|\Axvda", fsInfo[0]):
                print("EC2 instance has unsupported device and partition naming")
                sys.exit()
            elif fsInfo[2] != ("ext4" or "xfs"):
                print("EC2 instance has unsupported filesystem type")
                sys.exit()
            else:
                print("Obtained\n")
                return fsInfo
        elif inv["Status"] in ["Cancelled", "TimedOut", "Failed"]:
            print("Failed to obtain filesystem info:")
            print(inv["StatusDetails"])
            sys.exit()
        else:
            print("Still trying...")
            time.sleep(10)


def resize_volume(ec2, volumeId: str, currentSize: int, addSize: int):
    print("Resizing volume...")
    ec2.modify_volume(
        VolumeId=volumeId,
        Size=currentSize + addSize
    )
    time.sleep(10)
    while True:
        response = ec2.describe_volumes_modifications(
            VolumeIds=[
                volumeId
            ]
        )
        state = response['VolumesModifications'][0]['ModificationState']
        if state is None or state == 'completed':
            return
        elif state == 'failed':
            print("Volume resizing failed")
            sys.exit()
        else:
            time.sleep(10)


def ssm_exec_command(ssm, instanceId: str, command: str):
    print("Executing", command)
    response = ssm.send_command(
        InstanceIds=[instanceId],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
    )
    time.sleep(5)
    while True:
        inv = ssm.get_command_invocation(CommandId=response["Command"]["CommandId"],
                                         InstanceId=instanceId)

        if inv["Status"] == "Success":
            print("Done\n")
            return
        elif inv["Status"] in ["Cancelled", "TimedOut", "Failed"]:
            print("Failed to execute", command)
            print(inv["StatusDetails"], "\n", inv["StandardErrorContent"])
            sys.exit()
        else:
            time.sleep(5)


def extend_fs(ssm, instanceId: str, fsInfo: list):
    print("Resizing filesystem...")
    [deviceName, partitionName, fsType] = fsInfo
    growpart = "growpart /dev/{} {}"
    growpart = growpart.format(deviceName, partitionName.replace(deviceName + "p", "") if re.search("\Anvme", deviceName) else partitionName.replace(deviceName, ""))
    if fsType == "xfs":
        resize = "xfs_growfs -d /"
    else:
        resize = f"resize2fs /dev/{partitionName}"

    ssm_exec_command(ssm, instanceId, growpart)
    ssm_exec_command(ssm, instanceId, resize)

    print("Filesystem resized successfully")
    return



argParser = argparse.ArgumentParser()
argParser.add_argument("name", metavar='name', type=str, help="EC2 instance name")
argParser.add_argument("size", metavar='size', type=int, help="Size of adding disk space")
argParser.add_argument("-r", "--region", metavar='region', type=str, help="AWS region")
argParser.add_argument("-c", "--credentials", metavar=('key_id', 'secret'), nargs=2, type=str, help="Access key ID "
                                                                                                    "and Secret "
                                                                                                    "access key used "
                                                                                                    "to connect to "
                                                                                                    "AWS")

args = argParser.parse_args()

try:
    ec2Resource = boto3.resource('ec2',
                                 args.region,
                                 aws_access_key_id=args.credentials[0] if args.credentials else None,
                                 aws_secret_access_key=args.credentials[1] if args.credentials else None)
    ec2Client = boto3.client('ec2',
                             args.region,
                             aws_access_key_id=args.credentials[0] if args.credentials else None,
                             aws_secret_access_key=args.credentials[1] if args.credentials else None)
    ec2SSM = boto3.client('ssm',
                             args.region,
                             aws_access_key_id=args.credentials[0] if args.credentials else None,
                             aws_secret_access_key=args.credentials[1] if args.credentials else None)
except scrum.NoRegionError:
    print("Failed to connect. Region is not found in AWS config files. Try using -r (look --help for details) or "
          "specify AWS_DEFAULT_REGION variable.")
    sys.exit()
except scrum.NoCredentialsError:
    print("Failed to connect. No credentials were found in AWS config files. Try using -c (look --help for details).")
    sys.exit()

instances = list(ec2Resource.instances.filter(Filters=[
    {
        'Name': 'tag:Name',
        'Values': [args.name]
    },
    {
        'Name': 'instance-state-name',
        'Values': ['running']
    }
]))
if len(instances) == 0:
    print("There are no running instances with such tag")
    sys.exit()


print("Instance ID:", instances[0].id)


for volume in list(instances[0].volumes.all()):
    for attachment in volume.attachments:
        if attachment["InstanceId"] == instances[0].id and attachment["Device"] == ("/dev/sda1" or "/dev/xvda"):
            primaryVolumeId = attachment["VolumeId"]
            primaryVolumeCurrentSize = volume.size
            break

print("Primary volume ID:", primaryVolumeId)
print("Primary volume current size:", primaryVolumeCurrentSize, "\n")

#TODO: take volume snapshot

fs = get_fs_info(ec2SSM, instances[0].id)

resize_volume(ec2Client, primaryVolumeId, primaryVolumeCurrentSize, args.size)

extend_fs(ec2SSM, instances[0].id, fs)
