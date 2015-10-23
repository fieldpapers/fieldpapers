#!/usr/bin/env python

import boto3
import os, os.path, sys, time
import subprocess as sp
import functools, operator
from string import Template


def jsonf(p):
    return open(os.path.join('json', p)).read()


def get_valid_emails(aws):
    try:
        ses = aws.client('ses')
        addrs = ses.list_identities(IdentityType='EmailAddress')['Identities']
        addrstats = (ses.get_identity_verification_attributes(Identities=addrs)
                     ['VerificationAttributes'])
        vaddrs = [a for a in addrs if addrstats[a]['VerificationStatus'] == 'Success']
        doms = ses.list_identities(IdentityType='Domain')['Identities']
        domstats = (ses.get_identity_verification_attributes(Identities=doms)
                    ['VerificationAttributes'])
        vdoms = [d for d in doms if domstats[d]['VerificationStatus'] == 'Success']
        return vaddrs, vdoms
    except Exception as e:
        print('\n  FAILED TO LIST SES VERIFIED EMAIL IDENTITIES!\n')
        sys.exit(1)


def create_key_pair(aws, key_name):
    try:
        ec2 = aws.client('ec2')
        newkp = ec2.create_key_pair(KeyName=key_name)
    except Exception as e:
        print('\n  FAILED TO CREATE AWS KEY PAIR!\n')
        sys.exit(1)

    # Write key file for SSH.
    priv = os.path.expanduser('~/.ssh/' + key_name)
    with open(priv, 'w') as fp: print(newkp['KeyMaterial'], file=fp)
    os.chmod(priv, 0o600)
    try:
        genpub = sp.check_output(['ssh-keygen', '-yf', priv])
        with open(priv + '.pub', 'wb') as fp: fp.write(genpub)
        os.chmod(priv + '.pub', 0o600)
    except Exception as e:
        print('\n  FAILED TO CREATE PUBLIC KEY FOR AWS KEY PAIR!\n')
        sys.exit(1)


ec2_principals = { 'ap-northeast-1': 'ec2.amazonaws.com',
                   'ap-southeast-1': 'ec2.amazonaws.com',
                   'ap-southeast-2': 'ec2.amazonaws.com',
                   'cn-north-1':     'ec2.amazonaws.com.cn',
                   'eu-central-1':   'ec2.amazonaws.com',
                   'eu-west-1':      'ec2.amazonaws.com',
                   'sa-east-1':      'ec2.amazonaws.com',
                   'us-east-1':      'ec2.amazonaws.com',
                   'us-west-1':      'ec2.amazonaws.com',
                   'us-west-2':      'ec2.amazonaws.com' }


def create_service_role(aws, service_role, service_role_policy):
    assume_role_policy = jsonf('eb-service-role-assume-role-policy.json')
    role_policy = jsonf('eb-service-role-policy.json')

    try:
        iam = aws.client('iam')
        iam.create_role(RoleName=service_role,
                        AssumeRolePolicyDocument=assume_role_policy)
        p = iam.create_policy(PolicyName=service_role_policy,
                              PolicyDocument=role_policy)
        iam.attach_role_policy(RoleName=service_role, PolicyArn=p['Policy']['Arn'])
    except Exception as e:
        print('\n  FAILED CREATING ELASTIC BEANSTALK SERVICE ROLE!\n')
        print(e)
        print()
        sys.exit(1)


def create_app_role(aws, region, app_role, app_policy, instance_profile,
                    s3_bucket_name):
    ec2_principal = ec2_principals[region]
    assume_role_policy = (jsonf('eb-assume-role-policy.json').
                          replace('EC2_PRINCIPAL', ec2_principal))
    role_policy = (Template(jsonf('eb-policy.json.template'))
                   .substitute(bucket_name=s3_bucket_name))

    try:
        iam = aws.client('iam')
        iam.create_role(RoleName=app_role,
                        AssumeRolePolicyDocument=assume_role_policy)
        p = iam.create_policy(PolicyName=app_policy, PolicyDocument=role_policy)
        iam.attach_role_policy(RoleName=app_role, PolicyArn=p['Policy']['Arn'])

        iam.create_instance_profile(InstanceProfileName=instance_profile)
        iam.add_role_to_instance_profile(InstanceProfileName=instance_profile,
                                         RoleName=app_role)
    except Exception as e:
        print('\n  FAILED CREATING FIELD PAPERS APPLICATION ROLE!\n')
        print(e)
        print()
        sys.exit(1)


def create_s3_bucket(aws, s3_bucket_name, region):
    try:
        s3 = aws.client('s3')
        b = s3.create_bucket(Bucket=s3_bucket_name,
                             ACL='private',
                             CreateBucketConfiguration={
                                 'LocationConstraint': region
                             })
        s3.put_bucket_cors(Bucket=s3_bucket_name,
                           CORSConfiguration={
                               'CORSRules': [
                                   { 'AllowedHeaders': ['*'],
                                     'AllowedMethods': ['POST'],
                                     'AllowedOrigins': ['*'],
                                     'MaxAgeSeconds': 3000 },
                                   { 'AllowedMethods': ['GET'],
                                     'AllowedOrigins': ['*'] }]})
    except Exception as e:
        print('\n  FAILED CREATING S3 BUCKET!\n')
        print(e)
        print()
        sys.exit(1)


def create_eb_application(aws, app_name):
    eb = aws.client('elasticbeanstalk')
    try:
        eb.create_application(ApplicationName=app_name)
    except Exception as e:
        print('\n  FAILED CREATING ELASTIC BEANSTALK APPLICATION!\n')
        print(e)
        print()
        sys.exit(1)


def upload_app_version_zip(aws, s3_bucket_name, app_version_zip):
    s3 = aws.client('s3')
    try:
        s3.upload_file(app_version_zip, s3_bucket_name, app_version_zip)
    except Exception as e:
        print('\n  FAILED UPLOADING ELASTIC BEANSTALK SOURCE BUNDLE!\n')
        print(e)
        print()
        sys.exit(1)


EC2_INSTANCE_MEMORY = {
    't2.micro': 1, 't2.small': 2, 't2.medium': 4, 't2.large': 8,
    'm4.large': 8, 'm4.xlarge': 16, 'm4.2xlarge': 32,
    'm4.4xlarge': 64, 'm4.10xlarge': 160,
    'm3.medium': 3.75, 'm3.large': 7.5, 'm3.xlarge': 15, 'm3.2xlarge': 30,
    'c4.large': 3.75, 'c4.xlarge': 7.5, 'c4.2xlarge': 15,
    'c4.4xlarge': 30, 'c4.8xlarge': 60,
    'c3.large': 3.75, 'c3.xlarge': 7.5, 'c3.2xlarge': 15,
    'c3.4xlarge': 30, 'c3.8xlarge': 60,
    'r3.large': 15.25, 'r3.xlarge': 30.5, 'r3.2xlarge': 61,
    'r3.4xlarge': 122, 'r3.8xlarge': 244,
    'g2.2xlarge': 15, 'g2.8xlarge': 60,
    'i2.xlarge': 30.5, 'i2.2xlarge': 61, 'i2.4xlarge': 122, 'i2.8xlarge': 244,
    'd2.xlarge': 30.5, 'd2.2xlarge': 61, 'd2.4xlarge': 122, 'd2.8xlarge': 244
}

MEMORY_RESERVE = 128 # Mb

#===> NEED TO CHECK THESE
MEMORY_FRACTIONS = [('web', 2/7), ('tiler', 1/7), ('tasks', 4/7)]
MEMORY_MINIMUMS = [('web', 512), ('tiler', 128), ('tasks', 512)]

def calculate_memory_allocation(instance_type):
    total_mb = EC2_INSTANCE_MEMORY[instance_type] * 1024
    allocate_mb = total_mb - MEMORY_RESERVE
    mem = { t: int(v * allocate_mb) for t, v in MEMORY_FRACTIONS }
    for t, v in MEMORY_MINIMUMS:
        if mem[t] < v:
            print('\n  THIS INSTANCE TYPE DOES NOT HAVE ENOUGH MEMORY!'
                  '  CHOOSE A BIGGER ONE!')
            print()
            sys.exit(1)
    return mem


def create_eb_application_version(aws, app_name, app_version_label,
                                  s3_bucket_name, app_version_zip):
    eb = aws.client('elasticbeanstalk')
    try:
        eb.create_application_version(ApplicationName=app_name,
                                      VersionLabel=app_version_label,
                                      SourceBundle={
                                          'S3Bucket': s3_bucket_name,
                                          'S3Key': app_version_zip })
    except Exception as e:
        print('\n  FAILED CREATING ELASTIC BEANSTALK APPLICATION VERSION!\n')
        print(e)
        print()
        sys.exit(1)


def create_eb_environment(aws, region, env_name, app_name, cname_prefix,
                          app_version_label, key_name, instance_type,
                          instance_profile, service_role, db_instance_type):
    eb = aws.client('elasticbeanstalk')
    try:
        env = eb.create_environment(
            ApplicationName=app_name,
            EnvironmentName=env_name,
            CNAMEPrefix=cname_prefix,
            Tier={'Type': 'Standard', 'Name': 'WebServer', 'Version': ' '},
            VersionLabel=app_version_label,
            SolutionStackName=('64bit Amazon Linux 2015.03 v2.0.1 running '
                               'Multi-container Docker 1.6.2 (Generic)'),
            TemplateSpecification={
                'TemplateSnippets': [
                    { 'SnippetName': 'RdsExtensionEB',
                      'Order': 10000,
                      'SourceUrl': 'https://elasticbeanstalk-env-resources-' + region +
                                   '.s3.amazonaws.com/eb_snippets/rds/rds.json' }
                ]
            },
            OptionSettings=[
                { 'Namespace': 'aws:autoscaling:asg',
                  'OptionName': 'MaxSize', 'Value': '1',
                  'ResourceName': 'AWSEBAutoScalingGroup' },
                { 'Namespace': 'aws:autoscaling:asg',
                  'OptionName': 'MinSize', 'Value': '1',
                  'ResourceName': 'AWSEBAutoScalingGroup' },
                { 'Namespace': 'aws:autoscaling:launchconfiguration',
                  'OptionName': 'EC2KeyName', 'Value': key_name,
                  'ResourceName': 'AWSEBAutoScalingLaunchConfiguration' },
                { 'Namespace': 'aws:autoscaling:launchconfiguration',
                  'OptionName': 'IamInstanceProfile', 'Value': instance_profile,
                  'ResourceName': 'AWSEBAutoScalingLaunchConfiguration' },
                { 'Namespace': 'aws:autoscaling:launchconfiguration',
                  'OptionName': 'InstanceType', 'Value': instance_type,
                  'ResourceName': 'AWSEBAutoScalingLaunchConfiguration'},
                { 'Namespace': 'aws:elasticbeanstalk:environment',
                  'OptionName': 'EnvironmentType', 'Value': 'SingleInstance' },
                { 'Namespace': 'aws:elasticbeanstalk:environment',
                  'OptionName': 'ServiceRole', 'Value': service_role },
                { 'ResourceName': 'AWSEBRDSDatabase',
                  'OptionName': 'DBAllocatedStorage', 'Value': '5',
                  'Namespace': 'aws:rds:dbinstance' },
                { 'ResourceName': 'AWSEBRDSDatabase',
                  'OptionName': 'DBDeletionPolicy', 'Value': 'Delete',
                  'Namespace': 'aws:rds:dbinstance' },
                { 'ResourceName': 'AWSEBRDSDatabase',
                  'OptionName': 'DBEngine', 'Value': 'mysql',
                  'Namespace': 'aws:rds:dbinstance' },
                { 'ResourceName': 'AWSEBRDSDatabase',
                  'OptionName': 'DBInstanceClass', 'Value': db_instance_type,
                  'Namespace': 'aws:rds:dbinstance' },
                { 'OptionName': 'DBPassword', 'Value': 'fieldpapers',
                  'Namespace': 'aws:rds:dbinstance' },
                { 'OptionName': 'DBUser', 'Value': 'fieldpapers',
                  'Namespace': 'aws:rds:dbinstance' }])
    except Exception as e:
        print('\n  FAILED TO CREATE ELASTIC BEANSTALK ENVIRONMENT!\n')
        print(e)
        print()
        sys.exit(1)


def get_user_id(aws):
    iam = aws.client('iam')
    try:
        return iam.get_user()['User']['Arn'].split(':')[4]
    except Exception as e:
        print('\n  FAILED TO GET CURRENT AMAZON USER ID!\n')
        print(e)
        print()
        sys.exit(1)


def make_dockerrun(region, instance_type, s3_bucket_name,
                   smtp_access_key, smtp_secret_key,
                   mail_origin, base_url_host, secret_key, user_id):
    tmpl = Template(jsonf('Dockerrun.aws.json.template'))
    mem = calculate_memory_allocation(instance_type)
    repo = os.environ['FP_DOCKER_REPO'] if 'FP_DOCKER_REPO' in os.environ else 'fieldpapers'
    return tmpl.substitute(docker_repo=repo,
                           tasks_memory=mem['tasks'],
                           web_memory=mem['web'],
                           tiler_memory=mem['tiler'],
                           s3_bucket_name=s3_bucket_name,
                           region=region,
                           smtp_access_key=smtp_access_key,
                           smtp_secret_key=smtp_secret_key,
                           mail_origin=mail_origin,
                           base_url_host=base_url_host,
                           secret_key=secret_key,
                           user_id=user_id)


def elastic_beanstalk_environment_active(aws, env_name):
    eb = aws.client('elasticbeanstalk')
    try:
        return any(map(lambda e: e['Status'] == 'Ready',
                       [e for e in eb.describe_environments()['Environments']
                        if e['EnvironmentName'] == env_name]))
    except:
        print('\n\n  FAILED TO DETERMINE ENVIRONMENT STATUS!')
        sys.exit(1)


def find_eb_instance(aws, env_name):
    eb = aws.client('elasticbeanstalk')
    ec2 = aws.client('ec2')
    try:
        r = eb.describe_environment_resources(EnvironmentName=env_name)['EnvironmentResources']
        iid = r['Instances'][0]['Id']
        insts = functools.reduce(operator.add,
                                 [r['Instances']
                                  for r in ec2.describe_instances()['Reservations']])
        idx = list(map(lambda i: i['InstanceId'], insts)).index(iid)
        inst = insts[idx]
        return iid, inst['PublicDnsName'], inst['SecurityGroups'][0]['GroupId']
    except:
        print('\n\n  FAILED TO DETERMINE ENVIRONMENT INSTANCE DETAILS!')
        sys.exit(1)


def open_sg_port(aws, sg, port):
    ec2 = aws.client('ec2')
    try:
        ec2.authorize_security_group_ingress(
            GroupId=sg,
            IpProtocol='tcp', FromPort=port, ToPort=port,
            CidrIp='0.0.0.0/0')
    except:
        print('\n\n  FAILED TO ADD INGRESS RULE TO SECURITY GROUP!')
        sys.exit(1)



def add_ses_identity_policy(aws, region, role, user_id,
                            mail_origin, ses_identity_policy):
    ses = aws.client('ses')
    try:
        tmpl = Template(jsonf('ses-identity-policy.json.template'))
        pol = tmpl.substitute(region=region, user_id=user_id,
                              mail_origin=mail_origin, role=role)
        ses.put_identity_policy(Identity=mail_origin,
                                PolicyName=ses_identity_policy,
                                Policy=pol)
    except:
        print('\n\n  FAILED TO ADD EMAIL IDENTITY POLICY!')
        sys.exit(1)


def delete_resources(aws, key_name, service_role, service_role_policy,
                     app_role, app_policy, app_instance_profile,
                     s3_bucket_name, app_name, env_name,
                     mail_origin, ses_identity_policy):
    ec2 = aws.client('ec2')
    iam = aws.client('iam')
    s3 = aws.client('s3')
    eb = aws.client('elasticbeanstalk')
    ses = aws.client('ses')

    ps = iam.list_policies(Scope='Local')
    pdict = { p['PolicyName']:p['Arn'] for p in ps['Policies'] }
    rs = list(map(lambda r: r['RoleName'], iam.list_roles()['Roles']))
    ips = list(map(lambda i: i['InstanceProfileName'],
                   iam.list_instance_profiles()['InstanceProfiles']))
    bs = list(map(lambda b: b['Name'], s3.list_buckets()['Buckets']))
    kps = list(map(lambda k: k['KeyName'],
                   ec2.describe_key_pairs()['KeyPairs']))
    apps = list(map(lambda a: a['ApplicationName'],
                    eb.describe_applications()['Applications']))
    envs = [e['EnvironmentName'] for e in eb.describe_environments()['Environments']
            if e['Status'] != 'Terminated']
    ipols = ses.list_identity_policies(Identity=mail_origin)['PolicyNames']

    try:
        if app_name in apps:
            print('  Deleting Elastic Beanstalk application: ' + app_name)
            eb.delete_application(ApplicationName=app_name,
                                  TerminateEnvByForce=True)
            if env_name in envs:
                print('  Waiting for environment termination and application ')
                print('  deletion (this may take some time)')
                running = True
                start = time.time()
                while running:
                    time.sleep(5)
                    w = int(time.time() - start)
                    print('  WAITING: ', w // 60, 'm ', w % 60, 's   ',
                          sep='', end='\r', flush=True)
                    running = len([a for a in eb.describe_applications()['Applications']
                                   if a['ApplicationName'] == app_name]) > 0
                print('\n  Application deleted')
    except: print('    Failed to delete Elastic Beanstalk application!')

    try:
        if key_name in kps:
            print('  Deleting key pair: ' + key_name)
            ec2.delete_key_pair(KeyName=key_name)
            priv = os.path.expanduser('~/.ssh/' + key_name)
            if os.path.exists(priv): os.remove(priv)
            pub = priv + '.pub'
            if os.path.exists(pub): os.remove(pub)
    except: print('    Failed to delete key pair!')

    try:
        if app_instance_profile in ips:
            print('  Removing application role from instance profile')
            iam.remove_role_from_instance_profile(InstanceProfileName=app_instance_profile,
                                                  RoleName=app_role)
    except: print('    Failed to remove role from instance profile!')

    try:
        if app_instance_profile in ips:
            print('  Deleting instance profile: ' + app_instance_profile)
            iam.delete_instance_profile(InstanceProfileName=app_instance_profile)
    except: print('    Failed to delete instance profile!')

    try:
        if app_policy in pdict:
            print('  Detaching application role policy: ARN=' + pdict[app_policy])
            iam.detach_role_policy(RoleName=app_role, PolicyArn=pdict[app_policy])
    except: print('    Failed to detach application role policy!')

    try:
        if app_role in rs:
            print('  Deleting application role: ' + app_role)
            iam.delete_role(RoleName=app_role)
    except: print('    Failed to delete application role!')

    try:
        if service_role_policy in pdict:
            print('  Detaching service role policy: ARN=' + pdict[service_role_policy])
            iam.detach_role_policy(RoleName=service_role,
                                   PolicyArn=pdict[service_role_policy])
    except: print('    Failed to detach service role policy!')

    try:
        if service_role in rs:
            print('  Deleting service role: ' + service_role)
            iam.delete_role(RoleName=service_role)
    except: print('    Failed to delete service role!')

    try:
        if app_policy in pdict:
            print('  Deleting application policy: ' + app_policy)
            arn = PolicyArn=pdict[app_policy]
            pvs = iam.list_policy_versions(PolicyArn=arn)['Versions']
            for pv in pvs:
                if not pv['IsDefaultVersion']:
                    iam.delete_policy_version(PolicyArn=arn, VersionId=pv['VersionId'])
            iam.delete_policy(PolicyArn=arn)
    except: print('    Failed to delete application policy!')

    try:
        if service_role_policy in pdict:
            print('  Deleting service role policy: ' + service_role_policy)
            arn = PolicyArn=pdict[service_role_policy]
            pvs = iam.list_policy_versions(PolicyArn=arn)['Versions']
            for pv in pvs:
                if not pv['IsDefaultVersion']:
                    iam.delete_policy_version(PolicyArn=arn, VersionId=pv['VersionId'])
            iam.delete_policy(PolicyArn=arn)
    except: print('    Failed to delete service role policy!')

    try:
        if s3_bucket_name in bs:
            print('  Deleting S3 bucket: ' + s3_bucket_name)
            objs = s3.list_objects(Bucket=s3_bucket_name)
            while 'Contents' in objs:
                ds = [{ 'Key': o['Key'] } for o in objs['Contents']]
                s3.delete_objects(Bucket=s3_bucket_name,
                                  Delete={ 'Objects': ds })
                objs = s3.list_objects(Bucket=s3_bucket_name)
            s3.delete_bucket(Bucket=s3_bucket_name)
    except: print('    Failed to clean up S3 bucket!')

    try:
        if ses_identity_policy in ipols:
            print('  Deleting SES identity policy: ' + ses_identity_policy)
            ses.delete_identity_policy(Identity=mail_origin,
                                       PolicyName=ses_identity_policy)
    except: print('    Failed to clean up SES identity policy!')
