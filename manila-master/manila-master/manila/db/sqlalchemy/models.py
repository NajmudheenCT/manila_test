# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Piston Cloud Computing, Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
SQLAlchemy models for Manila data.
"""

from oslo_config import cfg
from oslo_db.sqlalchemy import models
from sqlalchemy import Column, Integer, String, schema
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import orm
from sqlalchemy import ForeignKey, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship, backref

from manila.common import constants

CONF = cfg.CONF
BASE = declarative_base()


class ManilaBase(models.ModelBase,
                 models.TimestampMixin,
                 models.SoftDeleteMixin):
    """Base class for Manila Models."""
    __table_args__ = {'mysql_engine': 'InnoDB'}
    metadata = None

    def to_dict(self):
        model_dict = {}
        for k, v in self.items():
            if not issubclass(type(v), ManilaBase):
                model_dict[k] = v
        return model_dict

    def soft_delete(self, session, update_status=False,
                    status_field_name='status'):
        """Mark this object as deleted."""
        if update_status:
            setattr(self, status_field_name, constants.STATUS_DELETED)

        return super(ManilaBase, self).soft_delete(session)

class Storage(BASE, ManilaBase):
    """Represents a storage object."""

    __tablename__ = 'storages'
    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    vendor = Column(String(255))
    model = Column(String(255))
    def __repr__(self):
       return "<Storage(name='%s', vendor='%s', model'%s')>" % (
                               self.name, self.vendor, self.model)


def register_models():
    """Register Models and create metadata.

    Called from manila.db.sqlalchemy.__init__ as part of loading the driver,
    it will never need to be called explicitly elsewhere unless the
    connection is lost and needs to be reestablished.
    """
    from sqlalchemy import create_engine
    model = (Storage
              )
    print('printing connection')
    print(CONF.database.connection)
    engine = create_engine('sqlite://', echo=False)
    model.metadata.create_all(engine)

class User(BASE):
    __tablename__ = 'users'

    # Every SQLAlchemy table should have a primary key named 'id'
    id = Column(Integer, primary_key=True)

    name = Column(String)
    fullname = Column(String)
    password = Column(String)

    # Lets us print out a user object conveniently.
    def __repr__(self):
       return "<User(name='%s', fullname='%s', password'%s')>" % (
                               self.name, self.fullname, self.password)

# The Address object stores the addresses
# of a user in the 'adressess' table.
class Address(BASE):
    __tablename__ = 'addresses'
    id = Column(Integer, primary_key=True)
    email_address = Column(String, nullable=False)

    # Since we have a 1:n relationship, we need to store a foreign key
    # to the users table.
    user_id = Column(Integer, ForeignKey('users.id'))

    # Defines the 1:n relationship between users and addresses.
    # Also creates a backreference which is accessible from a User object.
    user = relationship("User", backref=backref('addresses'))

    # Lets us print out an address object conveniently.
    def __repr__(self):
        return "<Address(email_address='%s')>" % self.email_address

class Volume(BASE):
    __tablename__ = 'volumes'

    # Every SQLAlchemy table should have a primary key named 'id'
    id = Column(Integer, primary_key=True)

    name = Column(String)
    fullname = Column(String)
    pool = Column(String)

    # Lets us print out a user object conveniently.
    def __repr__(self):
       return "<User(name='%s', fullname='%s', pool'%s')>" % (
                               self.name, self.fullname, self.pool)