#!/usr/bin/env python

import boto3
from botocore.loaders import Loader
import os, os.path, json, sys, textwrap, re, random, tempfile, time
from zipfile import ZipFile
import paramiko
from helpers import *

#----------------------------------------------------------------------
#
#  CONFIGURATION DATA HANDLING
#

config_file = '.aws-setup-config';

config = {
    'name_prefix':      None,
    'endpoint_host':    None,
    'email_origin':     None,
    'aws_region':       None,
    'instance_type':    't2.micro',
    'db_instance_type': 'db.t2.micro',
    's3_bucket_name':   None
}

def write_config():
    with open(config_file, 'w', encoding='utf-8') as fp:
        json.dump(config, fp)

def read_config():
    global config
    if os.path.exists(config_file):
        with open(config_file, encoding='utf-8') as fp:
            config = json.load(fp)

read_config()


#----------------------------------------------------------------------
#
#  USER AWS CREDENTIALS
#

# One of: ID and secret key environment variables; profile from
# command line or environment variable.  Don't proceed unless one of
# these is set up.

default_region = None
aws_profile = None
if len(sys.argv) == 3 and sys.argv[1] == '--profile':
    try:
        aws_profile = sys.argv[2]
        aws = boto3.session.Session(profile_name=aws_profile)
    except:
        print('FAILED TO CREATE AWS SESSION USING PROFILE "' +
              sys.argv[2] + '"')
        sys.exit(1)
    print('USING AWS CREDENTIAL PROFILE "' + sys.argv[2] + '"')
elif ('AWS_ACCESS_KEY_ID' in os.environ and
    'AWS_SECRET_ACCESS_KEY' in os.environ):
    print('USING AWS CREDENTIALS FROM ENVIRONMENT')
    try:
        aws = boto3.session.Session()
    except:
        print('FAILED TO CREATE AWS SESSION USING AWS_ACCESS_KEY_ID AND ' +
              'AWS_SECRET_ACCESS_KEY ENVIRONMENT VARIABLES')
        sys.exit(1)
elif 'AWS_PROFILE' in os.environ:
    try:
        aws_profile = os.environ['AWS_PROFILE']
        aws = boto3.session.Session(profile_name=aws_profile)
    except:
        print('FAILED TO CREATE AWS SESSION USING PROFILE "' +
              os.environ['AWS_PROFILE'] + '"')
        sys.exit(1)
    print('USING AWS CREDENTIAL PROFILE "' + os.environ['AWS_PROFILE'] + '"')
else:
    print("""
AWS CREDENTIALS ARE NOT SET UP

You need to create AWS credentials and either:

 - set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment
   variables, or

 - create a credentials profile using the AWS command line ("aws
   configure") and then either set the AWS_PROFILE environment
   variable or specify the environment on the command line using the
   '--profile' option.
""")
    sys.exit(1)


# Ho hum.  The version of the AWS API specification that comes with
# botocore seems to be out of date.  The following act of
# prestidigitation comes from the ebcli package (which is from Amazon,
# so is presumably reasonably kosher, although these things might
# constitute non-public interfaces) and ensures that the more recent
# API definition is picked up for Elastic Beanstalk API calls.

BOTOCORE_DATA_FOLDER_NAME = 'botocoredata'

def get_data_loader():
    # Creates a botocore data loader that loads custom data files
    # FIRST, creating a precedence for custom files.
    data_folder = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                               BOTOCORE_DATA_FOLDER_NAME)

    return Loader(extra_search_paths=[data_folder, Loader.BUILTIN_DATA_PATH],
                  include_default_search_paths=False)

def fix_aws_session(aws):
    aws._session.register_component('data_loader', get_data_loader())

fix_aws_session(aws)

default_region = aws._session.get_config_variable('region')
user_name = aws.client('iam').get_user()['User']['UserName']


valid_email_addresses, valid_email_domains = get_valid_emails(aws)
if len(valid_email_domains) == 0 and len(valid_email_addresses) == 0:
    print(textwrap.fill('There are no valid email addresses or domains you '
                        'can use as a mail origin!'))
    print()
    print('You need to set one up in the AWS SES console before proceeding.')


#----------------------------------------------------------------------
#
#  CONFIGURATION OPTIONS
#

def get_value(key, prompt, help, default=None, values=None, check=None):
    v = None
    if not default and config[key]: default = config[key]
    while not v:
        v = input(prompt +
                  (' [' + default +']' if default else '') + ': ')
        if v == '?':
            print()
            print(help, end='\n\n')
            v = None
        if v == '' and default: v = default
        if v and values and v not in values:
            msg = textwrap.fill('Invalid selection.  Must be one of: ' +
                                ', '.join(values))
            print('\n' + msg + '\n')
            v = ''
        if v and check and not check(v): v = ''
    config[key] = v
    write_config()

RDS_INSTANCES = [ 'db.m3.medium', 'db.m3.large', 'db.m3.xlarge',
                  'db.m3.2xlarge',
                  'db.r3.large', 'db.r3.xlarge', 'db.r3.2xlarge',
                  'db.r3.4xlarge', 'db.r3.8xlarge',
                  'db.t2.micro', 'db.t2.small', 'db.t2.medium', 'db.t2.large' ]

EC2_INSTANCES = [ 't2.micro', 't2.small', 't2.medium', 't2.large',
                  'm4.large', 'm4.xlarge', 'm4.2xlarge',
                  'm4.4xlarge', 'm4.10xlarge',
                  'm3.medium', 'm3.large', 'm3.xlarge', 'm3.2xlarge',
                  'c4.large', 'c4.xlarge', 'c4.2xlarge',
                  'c4.4xlarge', 'c4.8xlarge',
                  'c3.large', 'c3.xlarge', 'c3.2xlarge',
                  'c3.4xlarge', 'c3.8xlarge',
                  'r3.large', 'r3.xlarge', 'r3.2xlarge',
                  'r3.4xlarge', 'r3.8xlarge',
                  'g2.2xlarge', 'g2.8xlarge',
                  'i2.xlarge', 'i2.2xlarge', 'i2.4xlarge', 'i2.8xlarge',
                  'd2.xlarge', 'd2.2xlarge', 'd2.4xlarge', 'd2.8xlarge' ]


print("""

WELCOME TO THE FIELD PAPERS AWS QUICK-START SETUP SCRIPT

This script will ask for the information required to set up a simple
Field Papers instance on Amazon Web Services.  Once you've provided
the required information, the script will ask for confirmation, then
begin the process of setting the AWS resources needed to host Field
Papers.

To get help for any of the configuration options, just answer "?" at
the prompt.
""")

def prefix_check(p):
    if re.match('^[A-Za-z][A-Za-z0-9]*$' , p) is None:
        print('Prefix must be alphanumeric, e.g. "CadastaTest3"')
        return False
    else:
        return True

get_value('name_prefix', 'Installation name prefix',
"""This prefix is used to generate names for all the AWS entities to
be created.  For example, if the prefix is 'CadastaTest', then the
main IAM role for running the Field Papers instances will be called
'CadastaTestRole', and so on.  Must be alphanumeric.""",
          check=prefix_check)

def camel_to_snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()

prefix = config['name_prefix']
snprefix = camel_to_snake(prefix)

key_name = config['name_prefix'] + 'Key'
service_role_policy = prefix + 'ServiceRolePolicy'
app_policy = prefix + 'Policy'
service_role = prefix + 'ServiceRole'
app_role = prefix + 'Role'
app_instance_profile = prefix + 'InstanceProfile'
app_name = prefix + 'App'
env_name = prefix + 'Env'
cname_prefix = snprefix + '-env'
ses_identity_policy = prefix + 'EmailIdentityPolicy'

get_value('aws_region', 'AWS region',
"""AWS region in which to create all resources.""", default=default_region)

if config['aws_region'] != aws._session.get_config_variable('region'):
    if aws_profile:
        aws = boto3.session.Session(profile_name=aws_profile,
                                    region_name=config['aws_region'])
    else:
        aws = boto3.session.Session(region_name=config['aws_region'])
    fix_aws_session(aws)
aws_region = config['aws_region']

get_value('endpoint_host', 'Main endpoint host',
"""This is the host part of URL used to access the "front page" of Field
Papers.  The default value is the public-facing URL of the web server
Elastic Beanstalk instance this script will launch.  If you want to
use a custom URL instead in a domain that you control, you will need
to set up a DNS CNAME record to point from the name you want to use to
the Elastic Beanstalk URL.  (Once everything is set up, the script
will remind you to do this, and will tell you exactly what should go
in the CNAME record.)""",
          default=cname_prefix+'.'+aws_region+'.elasticbeanstalk.com')

endpoint_host = config['endpoint_host']

def check_email(email):
    if email in valid_email_addresses: return True
    ad = email.split('@')
    if len(ad) == 2 and ad[1] in valid_email_domains: return True
    print()
    print(textwrap.fill('Invalid selection.  Must either be a verified email '
                        'address or an email address from a verified domain.'))
    print()
    if len(valid_email_addresses) != 0:
        print('Valid email addresses:')
        print('\n'.join(map(lambda s: '  ' + s,
                            textwrap.wrap(', '.join(valid_email_addresses)))))
    if len(valid_email_domains) != 0:
        print('Valid email domains:')
        print('\n'.join(map(lambda s: '  ' + s,
                            textwrap.wrap(', '.join(valid_email_domains)))))
    print()
    return False

get_value('email_origin', 'Originating email address',
"""This is the email address that will be used by Field Papers to send
new account, password reset and similar emails.  This should be an
email address that has been verified for use by AWS's Simple Email
Service.  (See http://docs.aws.amazon.com/ses/latest/DeveloperGuide/verify-email-addresses.html)""",
          check=check_email)


def instance_help(type, name, instances):
    help = (type + ' instance type for the ' + name +
            '.  Must be one of the following:')
    help = textwrap.fill(help) + '\n\n'
    help += '\n'.join(map(lambda s: '  ' + s,
                          textwrap.wrap(', '.join(instances), 75)))
    return help

get_value('instance_type', 'EC2 instance type for Field Papers processes',
          instance_help('EC2', 'Field Papers processes', EC2_INSTANCES),
          values=EC2_INSTANCES)

get_value('db_instance_type', 'RDS instance type for MySQL database',
          instance_help('RDS', 'MySQL database', RDS_INSTANCES),
          values=RDS_INSTANCES)


get_value('s3_bucket_name', 'S3 bucket name',
"""Field Papers needs an S3 bucket to store page images and snapshots.
Choose a name for the bucket here.""",
          default=snprefix+'-bucket')


#----------------------------------------------------------------------
#
#  USER CONFIRMATION
#

s3_bucket_name = config['s3_bucket_name']
region = config['aws_region']
email_origin = config['email_origin']


# Write configuration summary.
print('\n\n')
print("""Configuration choices complete.  The script will now do the following:
""")
print(' 1. Delete all existing resources with conflicting names')
print(' 2. Create an AWS key pair:')
print('      ' + key_name)
print(' 3. Create IAM policies, roles and instance profile:')
print('      Policy: ' + service_role_policy)
print('      Policy: ' + app_policy)
print('      Role: ' + service_role)
print('      Role: ' + app_role)
print('      Instance profile: ' + app_instance_profile)
print(' 4. Create an S3 bucket:')
print('      ' + s3_bucket_name)
print(' 5. Create an Elastic Beanstalk application:')
print('      ' + app_name)
print(' 6. Create an Elastic Beanstalk application version')
print(' 7. Create an Elastic Beanstalk environment (with associated RDS instance):')
print('      ' + env_name)


# Create an Elastic Beanstalk application version files.

# Create Dockerrun.aws.json file.
secret_key = ''.join([random.choice('0123456789ABCDEF') for n in range(64)])
user_id = get_user_id(aws)
dockerrun = make_dockerrun(region, config['instance_type'], s3_bucket_name,
                           'DUMMY_SMTP_ACCESS_KEY', 'DUMMY_SMTP_SECRET_KEY',
                           email_origin, endpoint_host, secret_key, user_id)

app_version_label = 'fieldpapers-eb-app-v1'
app_version_zip = 'fieldpapers-eb-app-v1.zip'

with tempfile.TemporaryDirectory() as tmpdir:
    # Write Dockerrun.aws.json file.
    with open(os.path.join(tmpdir, 'Dockerrun.aws.json'), 'w') as fp:
        print(dockerrun, file=fp)

    # Create .ebextensions directory and files.
    os.mkdir(os.path.join(tmpdir, '.ebextensions'))
    with open(os.path.join(tmpdir, '.ebextensions/docker-user.config'), 'w') as fp:
        print('commands:', file=fp)
        print('  docker-user:', file=fp)
        print('    command: gpasswd -a ec2-user docker', file=fp)
    with open(os.path.join(tmpdir, '.ebextensions/rds.config'), 'w') as fp:
        print('Resources:', file=fp)
        print('    AWSEBRDSDatabase:', file=fp)
        print('        Type: AWS::RDS::DBInstance', file=fp)
        print('        Properties:', file=fp)
        print('            AllocatedStorage: 5', file=fp)
        print('            DBInstanceClass: ' + config['db_instance_type'], file=fp)
        print('            DBName: fieldpapers', file=fp)
        print('            Engine: mysql', file=fp)
        print('            MasterUsername: fieldpapers', file=fp)
        print('            MasterUserPassword: fieldpapers', file=fp)

    # Create application version ZIP file.
    with ZipFile(app_version_zip, 'w') as zip:
        for d, _, fs in os.walk(tmpdir):
            for f in fs:
                ff = os.path.join(d, f)
                zip.write(ff, os.path.relpath(ff, tmpdir))


# Check for permission to proceed.

resp = input('\nPermission to proceed?  Type YES to continue: ')
delete_only = False
if resp == 'DELETE':
    delete_only = True
elif resp != 'YES':
    sys.exit(0)
print()


#----------------------------------------------------------------------
#
#  SETUP
#

print('\nSTARTING:\n')

#--------------------------------------------------
# 1. Clean up any existing resources

print('Cleaning up existing resources...')
delete_resources(aws, key_name, service_role, service_role_policy,
                 app_role, app_policy, app_instance_profile,
                 s3_bucket_name, app_name, env_name,
                 email_origin, ses_identity_policy)
print()
if delete_only: sys.exit(0)


#--------------------------------------------------
# 2. Create AWS key pair

print('\nCreating AWS key pair...')
create_key_pair(aws, key_name)


#--------------------------------------------------
# 3. Create IAM policies, roles and instance profile

print('\nCreating IAM policies, roles and instance profile...')
create_service_role(aws, service_role, service_role_policy)
create_app_role(aws, region, app_role, app_policy, app_instance_profile,
                s3_bucket_name)


#--------------------------------------------------
# 4. Create an S3 bucket

print('\nCreating S3 bucket...')
create_s3_bucket(aws, s3_bucket_name, region)


#--------------------------------------------------
# 5. Create an Elastic Beanstalk application

print('\nCreating Elastic Beanstalk application...')
create_eb_application(aws, app_name)


#--------------------------------------------------
# 6. Create an Elastic Beanstalk application version

# Upload application version ZIP file to S3 bucket.
print('\nUploading application version ZIP file...')
upload_app_version_zip(aws, s3_bucket_name, app_version_zip)

# Create application version.
print('\nCreating Elastic Beanstalk application version...')
create_eb_application_version(aws, app_name, app_version_label,
                              s3_bucket_name, app_version_zip)


#--------------------------------------------------
# 7. Create an Elastic Beanstalk environment (with associated RDS instance)

# Create environment.
print('\nCreating Elastic Beanstalk environment...')
create_eb_environment(aws, region, env_name, app_name, cname_prefix,
                      app_version_label, key_name, config['instance_type'],
                      app_instance_profile, service_role,
                      config['db_instance_type'])


# Wait for environment to become active.
print("""

                  WAITING FOR ENVIRONMENT TO BECOME ACTIVE....

The environment may take quite a long time to become active.  AWS
needs to create an RDS database instance and all the associated
networking infrastructure (and it creates an initial database backup
as it does that), then needs to download the Docker containers for the
Field Papers components to initialise the EC2 instance used by Elastic
Beanstalk.

If you want to watch what's happening, you can log in to the AWS
Console in your browser and look on the Elastic Beanstalk page --
you'll see various events occurring as AWS sets up the resources to
run Field Papers.

Please be patient and do NOT interrupt this process while we're waiting!
""")
ready = False
start = time.time()
while not ready:
    time.sleep(5)
    w = int(time.time() - start)
    print('WAITING: ', w // 60, 'm ', w % 60, 's   ',
          sep='', end='\r', flush=True)
    ready = elastic_beanstalk_environment_active(aws, env_name)
print('\n')
print('ENVIRONMENT READY -- PERFORMING POST-SETUP TASKS...\n')


#--------------------------------------------------
# 8. Set up Rails database and precompile Rails assets

print('Connecting to EC2 instance...')
instance_id, instance_dns, instance_sg = find_eb_instance(aws, env_name)
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(instance_dns,
            username='ec2-user',
            key_filename=os.path.expanduser('~/.ssh/' + key_name),
            look_for_keys=False)

print('Loading schema into Rails database...')
try:
    ssh.exec_command('bash -c "WEBID=`docker ps | grep fp-web | cut -d\\  -f1` ; '
                     'docker exec \\$WEBID rake db:schema:load"')
except:
    print('  FAILED TO SET UP RAILS DATABASE!')


print('Precompiling Rails assets...')
try:
    ssh.exec_command('bash -c "WEBID=`docker ps | grep fp-web | cut -d\\  -f1` ; '
                     'docker exec \\$WEBID rake assets:precompile RAILS_ENV=production"')
    ssh.close()
except:
    print('  FAILED TO PRECOMPILE RAILS ASSETS!')


#--------------------------------------------------
# 9. Change EB security group permissions to open up port 8080.

print('\nOpening port 8080 on EC2 instance for tiler...')
try:
    open_sg_port(aws, instance_sg, 8080)
except:
    print('  FAILED TO OPEN PORT ON EC2 INSTANCE!')


#--------------------------------------------------
# 10. Set up SES identity policy to allow email sending from EC2 instance.

print('\nSetting up EC2/SES email identity policy...')
try:
    add_ses_identity_policy(aws, region, app_role, user_id,
                            email_origin, ses_identity_policy)
except:
    print('  FAILED TO ADD EMAIL IDENTITY POLICY!')


#----------------------------------------------------------------------
#
#  PRINT USEFUL INFORMATION:
#

print('\n\nALL SET UP!\n\n')

# EB application and environment information
print('AWS Elastic Beanstalk application: ' + app_name)
print('AWS Elastic Beanstalk environment: ' + env_name)

# URL for main endpoint
if endpoint_host == cname_prefix+'.'+aws_region+'.elasticbeanstalk.com':
    print('\nYour Field Papers instance should now be accessible at:\n')
    print('    http://' + endpoint_host)
    print()
else:
    print('Since you are not using the default Elastic Beanstalk endpoint name')
    print('you will need to set up a DNS CNAME record to redirect references')
    print('appropriately:\n')
    print(endpoint_host + '.  CNAME ' + snprefix + '-env.elasticbeanstalk.com' + '.\n')
    print('\nOnce the DNS changes have propagated, your Field Papers instance')
    print('should be accessible at:\n')
    print('    http://' + endpoint_host)
    print()

# EC2 instance name and DNS, plus SSH command to connect.
print('The EC2 instance running your Field Papers instance is:\n' +
      '  Instance ID: ' + instance_id + '\n' +
      '  Public DNS name: ' + instance_dns + '\n')
print('You can SSH to the instance with the following command:\n')
print('  ssh -l ec2-user -i ~/.ssh/' + key_name + ' ' + instance_dns)
print()
