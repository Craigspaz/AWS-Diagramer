import boto3

from diagrams import Cluster, Diagram, Node, Edge
from diagrams.aws.network import VPC
from diagrams.aws.network import PrivateSubnet, PublicSubnet, VPCElasticNetworkInterface
from diagrams.aws.compute import EC2Instance

ec2_client = boto3.client("ec2")

class _VPC:
    def __init__(self, vpc_id, name=None):
        self.name = name
        self.vpc_id = vpc_id
        self.subnets = []
        self.security_groups = []
    
    def add_subnet(self, subnet):
        self.subnets.append(subnet)

    def add_security_group(self, sg):
        self.security_groups.append(sg)
    
    def to_str(self):
        output = "VPC: " + str(self.vpc_id) + " : " + str(self.name) + "\n\tSubnets:\n"

        for subnet in self.subnets:
            output += "\t\t" + str(subnet.to_str()) + "\n"

        return output

class _Subnet:
    def __init__(self, subnet_id, cidr, name=None):
        self.subnet_id = subnet_id
        self.name = name
        self.cidr = cidr
        self.vpc_id = None
        self.public_subnet = False
        self.enis = []
        self.nacls = []

    def add_eni(self, eni):
        self.enis.append(eni)


    def add_nacl(self, nacl):
        self.nacls.append(nacl)

    def to_str(self):
        output = "Subnet: " + str(self.subnet_id) + " : " + str(self.name) + " : " + str(self.cidr) + "\n\t\tENIS: \n"
        
        for eni in self.enis:
            output += "\t\t\t" + str(eni.to_str()) + "\n"

        return output

class _ENI:
    def __init__(self, eni_id, subnet_id):
        self.eni_id = eni_id
        self.ip_address_mappings = []
        self.subnet_id = subnet_id
        self.security_groups = []

        self.diagram_obj = None
    
    def add_ip_mapping(self, ip, public_ip):
        self.ip_address_mappings.append({"IP": ip, "Public_IP": public_ip})
        
    def add_security_group(self, sg):
        self.security_groups.append(sg)

    def to_str(self):
        output = "ENI: " + str(self.eni_id) + " : IPs:\n"

        for ip_mapping in self.ip_address_mappings:
            output += "\t\t\t\t" + str("Private IP: " + str(ip_mapping["IP"]) + " | Public IP: " + str(ip_mapping["Public_IP"]))

        output += "\n\t\t\tSecurity Groups: \n"
        for sg in self.security_groups:
            output += "\t\t\t\t\t" + str(sg.sg_id) + " | " + str(sg.group_name)

        return output

class _EC2_Instance:
    def __init__(self, instance_id, name=None):
        self.instance_id = instance_id
        self.name = name
        self.state = None
        self.subnet_id = None
        self.vpc_id = None
        self.enis = []

        self.diagram_obj = None
    
    def add_eni(self, eni):
        self.enis.append(eni)

class _Security_Group:
    def __init__(self, sg_id, vpc_id, group_name):
        self.sg_id = sg_id
        self.vpc_id = vpc_id
        self.group_name = group_name

class _Network_ACL:
    def __init__(self, network_acl_id):
        self.network_acl_id = network_acl_id
        self.subnets = []

    def add_subnet(self, nacl):
        self.subnets.append(nacl)

def get_vpcs():
    print("Fetching VPC")

    list_vpcs = []

    paginationToken = None
    while True:
        if paginationToken == None:
            vpcs = ec2_client.describe_vpcs()
        else:
            vpcs = ec2_client.describe_vpcs(NextToken=paginationToken)
        if vpcs is not None:
            for vpc in vpcs["Vpcs"]:
                v = _VPC(vpc["VpcId"])
                if "Tags" in vpc:
                    for tag in vpc["Tags"]:
                        if tag["Key"] == "Name":
                            v.name = tag["Value"]
                            break
                list_vpcs.append(v)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_vpcs

def get_subnets(vpcs):
    print("Fetching subnets")
    list_subnets = []

    paginationToken = None
    while True:
        if paginationToken == None:
            subnets = ec2_client.describe_subnets()
        else:
            subnets = ec2_client.describe_subnets(NextToken=paginationToken)
        if subnets is not None:
            for subnet in subnets["Subnets"]:
                s = _Subnet(subnet["SubnetId"], subnet["CidrBlock"])
                s.vpc_id = subnet["VpcId"]

                if "Tags" in subnet:
                    for tag in subnet["Tags"]:
                        if tag["Key"] == "Name":
                            s.name = tag["Value"]
                            break
                
                for vpc in vpcs:
                    if vpc.vpc_id == s.vpc_id:
                        vpc.add_subnet(s)
                        break
                list_subnets.append(s)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_subnets

def get_eni(subnets, sgs):
    print("Fetch ENI")
    list_eni = []

    paginationToken = None
    while True:
        if paginationToken == None:
            enis = ec2_client.describe_network_interfaces()
        else:
            enis = ec2_client.describe_network_interfaces(NextToken=paginationToken)
        if enis is not None:
            for eni in enis["NetworkInterfaces"]:
                interface_id = eni["NetworkInterfaceId"]
                e = _ENI(interface_id, eni["SubnetId"])
                for ip in eni["PrivateIpAddresses"]:
                    private_ip = ip["PrivateIpAddress"]
                    public_ip = None
                    if "Association" in ip and "PublicIp" in ip["Association"]:
                        public_ip = ip["Association"]["PublicIp"]
                    e.add_ip_mapping(private_ip, public_ip)

                for group in eni["Groups"]:
                    group_id = group["GroupId"]
                    for sg in sgs:
                        if sg.sg_id == group_id:
                            e.add_security_group(sg)
                            break

                if "TagSet" in eni:
                    for tag in eni["TagSet"]:
                        if tag["Key"] == "Name":
                            e.name = tag["Value"]
                            break
                
                for subnet in subnets:
                    if subnet.subnet_id == e.subnet_id:
                        subnet.add_eni(e)
                        break
                list_eni.append(e)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_eni

def get_ec2_instances(enis):
    print("Fetching Ec2 Instances")
    list_ec2_instances = []

    paginationToken = None
    while True:
        if paginationToken == None:
            reservations = ec2_client.describe_instances()
        else:
            reservations = ec2_client.describe_instances(NextToken=paginationToken)
        if reservations is not None:
            for reservation in reservations["Reservations"]:
                for instance in reservation["Instances"]:
                    i = _EC2_Instance(instance["InstanceId"])
                    if "State" in instance:
                        i.state = instance["State"]["Name"]
                    i.subnet_id = instance["SubnetId"]
                    i.vpc_id = instance["VpcId"]
                    
                    for network_interface in instance["NetworkInterfaces"]:
                        interface_id = network_interface["NetworkInterfaceId"]
                        for eni in enis:
                            if eni.eni_id == interface_id:
                                i.add_eni(eni)
                                break

                    if "Tags" in instance:
                        for tag in instance["Tags"]:
                            if tag["Key"] == "Name":
                                i.name = tag["Value"]
                                break

                    list_ec2_instances.append(i)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_ec2_instances

def get_security_groups(vpcs):
    print("Fetching security groups")
    list_security_groups = []

    paginationToken = None
    while True:
        if paginationToken == None:
            sgs = ec2_client.describe_security_groups()
        else:
            sgs = ec2_client.describe_security_groups(NextToken=paginationToken)
        if sgs is not None:
            for sg in sgs["SecurityGroups"]:
                group_name = sg["GroupName"]
                group_id = sg["GroupId"]
                vpc_id = sg["VpcId"]

                s = _Security_Group(group_id, vpc_id, group_name)

                for vpc in vpcs:
                    if vpc.vpc_id == vpc_id:
                        vpc.add_security_group(s)

                list_security_groups.append(s)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_security_groups

def get_network_acl(subnets):
    print("Fetching Network Acl")
    list_network_acl = []

    paginationToken = None
    while True:
        if paginationToken == None:
            nacls = ec2_client.describe_network_acls()
        else:
            nacls = ec2_client.describe_network_acls(NextToken=paginationToken)
        if nacls is not None:
            for nacl in nacls["NetworkAcls"]:
                
                # TODO: Identify if a subnet is a public or private subnet
                n = _Network_ACL(nacl["NetworkAclId"])
                for association in nacl["Associations"]:
                    subnet_id = association["SubnetId"]
                    for subnet in subnets:
                        if subnet.subnet_id == subnet_id:
                            n.add_subnet(subnet)
                            subnet.add_nacl(n)
                            break

                list_network_acl.append(n)
            if "NextToken" in vpcs:
                paginationToken = vpcs["NextToken"]
            else:
                break
            
    return list_network_acl

vpcs = get_vpcs()
subnets = get_subnets(vpcs)
sgs = get_security_groups(vpcs)
enis = get_eni(subnets, sgs)
nacls = get_network_acl(subnets)
ec2_instances = get_ec2_instances(enis)


with Diagram("AWS Account", show=False):

    for v in vpcs:
        print(v.to_str())

        vpc_str = v.vpc_id
        if v.name != None:
            vpc_str += "|" + str(v.name)
        with Cluster(vpc_str):
            for subnet in v.subnets:
                subnet_str = subnet.subnet_id
                if subnet.name != None:
                    subnet_str += "|" + str(subnet.name)

                if subnet.public_subnet:
                    with Cluster(subnet_str):
                        for eni in subnet.enis:
                            sg_str = ""
                            for sg in eni.security_groups:
                                sg_str += sg.sg_id + "|" + str(sg.group_name) + "\n"
                            with Cluster(sg_str):
                                eni.diagram_obj = VPCElasticNetworkInterface(eni.eni_id)

                else:
                    with Cluster(subnet_str):
                        for eni in subnet.enis:
                            sg_str = ""
                            for sg in eni.security_groups:
                                sg_str += sg.sg_id + "|" + str(sg.group_name) + "\n"
                            with Cluster(sg_str):
                                eni.diagram_obj = VPCElasticNetworkInterface(eni.eni_id)
            for ec2_instance in ec2_instances:
                if ec2_instance.vpc_id == v.vpc_id:
                    ec2_instance_str = ec2_instance.instance_id
                    if ec2_instance.name != None:
                        ec2_instance_str += "|" + str(ec2_instance.name)
                    e = EC2Instance(ec2_instance_str)
                    ec2_instance.diagram_obj = e
                    for eni in ec2_instance.enis:
                        if e != None and eni.diagram_obj != None:
                            e - Edge(minlen="3") - eni.diagram_obj
