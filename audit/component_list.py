#!/usr/bin/env python

# aws-vault exec fp ./component_list.py

import boto.ec2
import boto.rds
import pprint

def main():
    for region in regions():
        print region
        i_info = instance_info(region)
        d_info = db_info(region)
        if i_info:
            pprint.pprint(i_info)
        if d_info:
            pprint.pprint(d_info)

def regions():
    regions = boto.ec2.connect_to_region('us-east-1').get_all_regions()
    regions = [region.name for region in regions]
    return regions

def instance_info(region):
    ec2 = boto.ec2.connect_to_region(region)
    info = {}
    instances = ec2.get_only_instances(filters={'instance-state-name': 'running'})
    for instance in instances:
        info[instance.id] = {'region': region, 'ami_id': instance.image_id}
        ami_desc = ec2.get_all_images(instance.image_id)
        if ami_desc:
            info[instance.id]['ami_desc'] = ami_desc[0].description
    return info

def db_info(region):
    rds = boto.rds.connect_to_region(region)
    info = {}
    instances = rds.get_all_dbinstances()
    for instance in instances:
        info[instance.id] = {'region': region, 'engine': instance.engine}
    return info

if __name__ == '__main__':
    main()
