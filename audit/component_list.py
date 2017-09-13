#!/usr/bin/env python

# aws-vault exec fp ./component_list.py

import boto.ec2
import boto.rds

def regions():
    regions = boto.ec2.connect_to_region('us-east-1').get_all_regions()
    regions = [region.name for region in regions]
    return regions

def instance_info(region):
    ec2 = boto.ec2.connect_to_region(region)
    info = {}
    instances = ec2.get_only_instances()
    for instance in instances:
        info[instance.id] = {
                                     'region': region,
                                     'ami_id': instance.image_id,
                                     'ami_desc': ec2.get_all_images(instance.image_id)[0].description
                                     }
    return info

def db_info(region):
