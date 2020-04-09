#!/usr/bin/env python

# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

"""Starter script for manila OS API."""

import eventlet
import manila.db
from manila import context, db
from manila.db.sqlalchemy.models import register_models

eventlet.monkey_patch()

import sys

from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF


def main():
   # register_models()
   # ctxt = context.RequestContext('admin', 'fake', True)

   # sshare = db.storage_create(ctxt, {})
   # result=db.storage_get(ctxt,123)
   # print(result)
   db.create_volume()
   db.print_volume()



if __name__ == '__main__':
    main()
