**CLI tool for resizing EBS primary volumes**

Usage:
`python main.py [-rch] [--region --credentials --help] ec2InstanceName addingSpace`

This tool is applicable only to linux EC2 instances with xfs or ext4 filesystems.
Please make sure that SSM is enabled for dark magic to happen.

To use this tool you must provide it AWS credentials and region using one of these methods:
1. If you have aws cli installed run `aws configure` to set up default region and credentials
2. Create ~/.aws/credentials file with the following content:
   ```
   [default]
   region=us-west-2
   aws_access_key_id = AKIAIOSFODNN7EXAMPLE
   aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   ```
3. Pass region and credentials as arguments (see --help for details)
4. (Not recommended) Set environmental variables:
   ```
   export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
   export AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
   export AWS_DEFAULT_REGION=us-west-2
   ```
   
