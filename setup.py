import json
import pprint
import boto3
import dns.resolver
import yaml
from requests import get
import subprocess

dns_resolver = dns.resolver.Resolver()
pp = pprint.PrettyPrinter(indent=2)

#==[local functions]============================================================

# output structure to stdout
def print_r(stuff):
    pp.pprint(stuff)
    print('=====')
    

# get info on named broker
def get_aws_route_table(route_table_name, region):
    client_ec2 = boto3.client('ec2', region_name=region)

    response = client_ec2.describe_route_tables(
        Filters=[{'Name': 'tag:Name', 'Values': [route_table_name]}]
    )

    rt_info = {
        'rt_id': response['RouteTables'][0]['RouteTableId']
    }

    return rt_info

# get info on peering connection by cidr_block
def get_peering_connection_info(cidr_block, region):
    client_vpc = boto3.client('ec2', region_name=region)

    response = client_vpc.describe_vpc_peering_connections(
        Filters=[{'Name': 'accepter-vpc-info.cidr-block', 'Values': [cidr_block]}]
    )

    pcx_info = {
        'pcx_id': response['VpcPeeringConnections'][0]['VpcPeeringConnectionId']
    }

    return pcx_info

# add vpc peering connection
def add_peering_route(rt_id, cidr_block, pcx_id, region):
    client_ec2 = boto3.client('ec2', region)
    response = client_ec2.create_route(
        DestinationCidrBlock = cidr_block,
        VpcPeeringConnectionId = pcx_id,
        RouteTableId = rt_id,
    )
    return response

# create cloudformation stack with provided yaml
def aws_create_stack(stack_name, template_file, stack_params, region):

    with open(template_file) as f:
        stack_yaml = f.read()

    # test passing parameters in
    client_cf = boto3.client('cloudformation', region_name=region)
    response = client_cf.create_stack(
        StackName = stack_name,
        TemplateBody = stack_yaml,
        Parameters = stack_params,
    )

    # block until stack creation complete
    waiter = client_cf.get_waiter('stack_create_complete')
    waiter.wait(StackName=stack_name)

    return response

# get info on named broker
def get_amazon_mq_broker_info(broker_name, region):
    client_mq = boto3.client('mq', region_name=region)

    brokers = client_mq.list_brokers()
    broker_info = {}

    for broker in brokers['BrokerSummaries']:

        if broker['BrokerName'] == broker_name:
            broker_arn =  broker['BrokerArn']
            broker_id =  broker['BrokerId']
            broker_name =  broker['BrokerName']
            broker_region = broker_arn.split(':')[3]
            broker_url = f"{broker_id}.mq.{broker_region}.amazonaws.com"
            broker_ips = []

            for broker_ip in dns_resolver.resolve(broker_url, 'A'):
                broker_ips.append(broker_ip.to_text())

            broker_info = {
                'arn':  broker_arn,
                'id': broker_id,
                'name': broker_name,
                'region': broker_region,
                'url': broker_url,
                'ips': broker_ips,
            }

    return broker_info


#==[main]=======================================================================

# create infrastructure in second region (us-east-2)
infrastructure = {
    'oregon': {
        'pcx': '',
        'rt': '',
        'broker_id': '',
        'broker_url': '',
    },
    'ohio': {
        'pcx': '',
        'rt': '',
        'broker_id': '',
        'broker_url': '',
    }
}

# 1. create cloud formation stack (for second region)
if True:
    print(f'creating stack {vpc_name}. please wait... (~30 seconds)')

    aws_create_stack('', 'workshop-stack-ohio.yaml', 'us-east-2', 
        [{'ParameterKey': 'WorkshopRemoteVpcId', 'ParameterValue': 'WorkshopRemoteVpcId'}]
        
    )

# 2. get peering connection info
pcx_info = get_peering_connection_info('10.11.0.0/24', 'us-west-2')
infrastructure['oregon']['pcx'] = pcx_info['pcx_id']
infrastructure['ohio']['pcx'] = pcx_info['pcx_id']

# 3. get route tables information
rt_info = get_aws_route_table('WorkshopRouteTable', 'us-west-2')
infrastructure['oregon']['rt'] = rt_info['rt_id']
rt_info = get_aws_route_table('WorkshopRouteTable', 'us-east-2')
infrastructure['ohio']['rt'] = rt_info['rt_id']

# 4. add vpc peering routes
add_peering_route(infrastructure['oregon']['rt'], '10.14.0.0/24', infrastructure['oregon']['pcx'], 'us-west-2')


#--[setup reverse proxy]--------------------------------------------------------

# 1. get broker information (needed to configure caddy reverse proxy
broker_1 = get_amazon_mq_broker_info('WorkshopBroker1', 'us-west-2')
infrastructure['oregon']['broker_id'] = broker_1['id']
infrastructure['oregon']['broker_url'] = broker_1['url']

broker_2 = get_amazon_mq_broker_info('WorkshopBroker2', 'us-east-2')
infrastructure['ohio']['broker_id'] = broker_2['id']
infrastructure['ohio']['broker_url'] = broker_2['url']

# define caddyfile content (reverse proxy configuration)
if True:
    caddyfile = ":2080 {\n"
    caddyfile += f"	reverse_proxy https://{broker_1['id']}.mq.{broker_1['region']}.amazonaws.com:443\n"
    caddyfile += "}\n:2081  {\n"
    caddyfile += f"	reverse_proxy https://{broker_2['id']}.mq.{broker_2['region']}.amazonaws.com:443\n"
    caddyfile += "}"

    # create caddyfile
    fh = open('Caddyfile', 'w')
    fh.write(caddyfile)
    fh.close()

    # start caddy server
    subprocess.run(['caddy', 'start']) 

# information
print_r(infrastructure)

# get ip addresses for public access to rabbit mq
public_ip = get('https://api.ipify.org').content.decode('utf8')
print(f"public ip: https://{public_ip}:2080")
print(f"public ip: https://{public_ip}:2081")
