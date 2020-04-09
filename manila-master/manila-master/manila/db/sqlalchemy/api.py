# Copyright (c) 2011 X.commerce, a business unit of eBay Inc.
# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright (c) 2014 Mirantis, Inc.
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

"""Implementation of SQLAlchemy backend."""

import copy
import datetime
from functools import wraps
import ipaddress
import sys
import warnings

# NOTE(uglide): Required to override default oslo_db Query class
import manila.db.sqlalchemy.query  # noqa

from oslo_config import cfg
from oslo_db import api as oslo_db_api
from oslo_db import exception as db_exc
from oslo_db import exception as db_exception
from oslo_db import options as db_options
from oslo_db.sqlalchemy import session
from oslo_db.sqlalchemy import utils as db_utils
from oslo_log import log
from oslo_utils import excutils
from oslo_utils import timeutils
from oslo_utils import uuidutils
import six
from sqlalchemy import MetaData, create_engine
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, sessionmaker
from sqlalchemy.orm import subqueryload
from sqlalchemy.sql.expression import literal
from sqlalchemy.sql.expression import true
from sqlalchemy.sql import func

from manila import exception
from manila.db.sqlalchemy import models
from manila.db.sqlalchemy.models import Storage, User, Address, Volume

CONF = cfg.CONF

LOG = log.getLogger(__name__)


_DEFAULT_QUOTA_NAME = 'default'
PER_PROJECT_QUOTAS = []

_FACADE = None

_DEFAULT_SQL_CONNECTION = 'sqlite:///:memory:'
db_options.set_defaults(cfg.CONF,
                        connection=_DEFAULT_SQL_CONNECTION)

engine = create_engine('sqlite:///:memory:', echo=False)
model = Storage
model.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

def create_volume():
    ed_user = Volume(name='vmax_vol', fullname='vmax_vol pool 1 ', pool='pool1')
     # Let's add the user and its addresses we've created to the DB and commit.
    session.add(ed_user)
    session.commit()

def print_volume():
    volume_by_id= session.query(Volume) \
        .filter(Volume.name == 'vmax_vol') \
        .first()

    print(volume_by_id)



def create_user():
    ed_user = User(name='ed', fullname='Ed Jones', password='edspassword')
    ed_user.addresses = [Address(email_address='ed@google.com'), Address(email_address='e25@yahoo.com')]

    # Let's add the user and its addresses we've created to the DB and commit.
    session.add(ed_user)
    session.commit()
def print_user():
    user_by_email = session.query(User) \
        .filter(Address.email_address == 'ed@google.com') \
        .first()

    print(user_by_email)

    # This will cause an additional query by lazy loading from the DB.
    print(user_by_email.addresses)

    # To avoid querying again when getting all addresses of a user,
    # we use the joinedload option. SQLAlchemy will load all results and hide
    # the duplicate entries from us, so we can then get for
    # the user's addressess without an additional query to the DB.
    user_by_email = session.query(User) \
        .filter(Address.email_address == 'ed@google.com') \
        .options(joinedload(User.addresses)) \
        .first()

    print(user_by_email)
    print(user_by_email.addresses)

def test():
    print('hello')

def storage_get(context, storage_id):
    model = Storage
    storage_instance = session.query(model) \
        .filter(id==123) \
        .first()
    return storage_instance


def storage_create(context, storage_id):
    model = Storage

    print("am in sqalchem now")
    storage_ref = models.Storage()
    storage_ref.id = storage_id
    storage_ref.name = "MY anme"
    storage_ref.model = 'VMAX'
    storage_ref.vendor = 'EMC'
    storage_ref.save(session=session)
    return storage_ref


def _create_facade_lazily():
    global _FACADE
    if _FACADE is None:
        _FACADE = session.EngineFacade.from_config(cfg.CONF)
    return _FACADE


def get_engine():
    facade = _create_facade_lazily()
    return facade.get_engine()


def get_session(**kwargs):
    facade = _create_facade_lazily()
    return facade.get_session(**kwargs)


def get_backend():
    """The backend is this module itself."""

    return sys.modules[__name__]


def is_admin_context(context):
    """Indicates if the request context is an administrator."""
    if not context:
        warnings.warn(_('Use of empty request context is deprecated'),
                      DeprecationWarning)
        raise Exception('die')
    return context.is_admin


def is_user_context(context):
    """Indicates if the request context is a normal user."""
    if not context:
        return False
    if context.is_admin:
        return False
    if not context.user_id or not context.project_id:
        return False
    return True


def authorize_project_context(context, project_id):
    """Ensures a request has permission to access the given project."""
    if is_user_context(context):
        if not context.project_id:
            raise exception.NotAuthorized()
        elif context.project_id != project_id:
            raise exception.NotAuthorized()


def authorize_user_context(context, user_id):
    """Ensures a request has permission to access the given user."""
    if is_user_context(context):
        if not context.user_id:
            raise exception.NotAuthorized()
        elif context.user_id != user_id:
            raise exception.NotAuthorized()


def authorize_quota_class_context(context, class_name):
    """Ensures a request has permission to access the given quota class."""
    if is_user_context(context):
        if not context.quota_class:
            raise exception.NotAuthorized()
        elif context.quota_class != class_name:
            raise exception.NotAuthorized()


def require_admin_context(f):
    """Decorator to require admin request context.

    The first argument to the wrapped function must be the context.

    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin_context(args[0]):
            raise exception.AdminRequired()
        return f(*args, **kwargs)
    return wrapper


def require_context(f):
    """Decorator to require *any* user or admin context.

    This does no authorization for user or project access matching, see
    :py:func:`authorize_project_context` and
    :py:func:`authorize_user_context`.

    The first argument to the wrapped function must be the context.

    """
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_admin_context(args[0]) and not is_user_context(args[0]):
            raise exception.NotAuthorized()
        return f(*args, **kwargs)
    return wrapper




def handle_db_data_error(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except db_exc.DBDataError:
            msg = _('Error writing field to database.')
            LOG.exception(msg)
            raise exception.Invalid(msg)

    return wrapper


def model_query(context, model, *args, **kwargs):
    """Query helper that accounts for context's `read_deleted` field.

    :param context: context to query under
    :param model: model to query. Must be a subclass of ModelBase.
    :param session: if present, the session to use
    :param read_deleted: if present, overrides context's read_deleted field.
    :param project_only: if present and context is user-type, then restrict
            query to match the context's project_id.
    """
    session = kwargs.get('session') or get_session()
    read_deleted = kwargs.get('read_deleted') or context.read_deleted
    project_only = kwargs.get('project_only')
    kwargs = dict()

    if project_only and not context.is_admin:
        kwargs['project_id'] = context.project_id
    if read_deleted in ('no', 'n', False):
        kwargs['deleted'] = False
    elif read_deleted in ('yes', 'y', True):
        kwargs['deleted'] = True

    return db_utils.model_query(
        model=model, session=session, args=args, **kwargs)


def exact_filter(query, model, filters, legal_keys,
                 created_at_key='created_at'):
    """Applies exact match filtering to a query.

    Returns the updated query.  Modifies filters argument to remove
    filters consumed.

    :param query: query to apply filters to
    :param model: model object the query applies to, for IN-style
                  filtering
    :param filters: dictionary of filters; values that are lists,
                    tuples, sets, or frozensets cause an 'IN' test to
                    be performed, while exact matching ('==' operator)
                    is used for other values
    :param legal_keys: list of keys to apply exact filtering to
    """

    filter_dict = {}
    created_at_attr = getattr(model, created_at_key, None)
    # Walk through all the keys
    for key in legal_keys:
        # Skip ones we're not filtering on
        if key not in filters:
            continue

        # OK, filtering on this key; what value do we search for?
        value = filters.pop(key)

        if key == 'created_since' and created_at_attr:
            # This is a reserved query parameter to indicate resources created
            # after a particular datetime
            value = timeutils.normalize_time(value)
            query = query.filter(created_at_attr.op('>=')(value))
        elif key == 'created_before' and created_at_attr:
            # This is a reserved query parameter to indicate resources created
            # before a particular datetime
            value = timeutils.normalize_time(value)
            query = query.filter(created_at_attr.op('<=')(value))
        elif isinstance(value, (list, tuple, set, frozenset)):
            # Looking for values in a list; apply to query directly
            column_attr = getattr(model, key)
            query = query.filter(column_attr.in_(value))
        else:
            # OK, simple exact match; save for later
            filter_dict[key] = value

    # Apply simple exact matches
    if filter_dict:
        query = query.filter_by(**filter_dict)

    return query


def ensure_model_dict_has_id(model_dict):
    if not model_dict.get('id'):
        model_dict['id'] = uuidutils.generate_uuid()
    return model_dict



@require_context
def quota_get_all(context, project_id):
    authorize_project_context(context, project_id)

    result = (model_query(context, models.ProjectUserQuota).
              filter_by(project_id=project_id).
              all())

    return result


@require_admin_context
def quota_create(context, project_id, resource, limit, user_id=None,
                 share_type_id=None):
    per_user = user_id and resource not in PER_PROJECT_QUOTAS

    if per_user:
        check = model_query(context, models.ProjectUserQuota).filter(
            models.ProjectUserQuota.project_id == project_id,
            models.ProjectUserQuota.user_id == user_id,
            models.ProjectUserQuota.resource == resource,
        ).all()
        quota_ref = models.ProjectUserQuota()
        quota_ref.user_id = user_id
    elif share_type_id:
        check = model_query(context, models.ProjectShareTypeQuota).filter(
            models.ProjectShareTypeQuota.project_id == project_id,
            models.ProjectShareTypeQuota.share_type_id == share_type_id,
            models.ProjectShareTypeQuota.resource == resource,
        ).all()
        quota_ref = models.ProjectShareTypeQuota()
        quota_ref.share_type_id = share_type_id
    else:
        check = model_query(context, models.Quota).filter(
            models.Quota.project_id == project_id,
            models.Quota.resource == resource,
        ).all()
        quota_ref = models.Quota()
    if check:
        raise exception.QuotaExists(project_id=project_id, resource=resource)

    quota_ref.project_id = project_id
    quota_ref.resource = resource
    quota_ref.hard_limit = limit
    session = get_session()
    with session.begin():
        quota_ref.save(session)
    return quota_ref







@require_context
def backend_info_create(context, host, value):
    session = get_session()
    with session.begin():
        info_ref = models.BackendInfo()
        info_ref.update({"host": host,
                         "info_hash": value})
        info_ref.save(session)
        return info_ref


@require_context
def backend_info_update(context, host, value=None, delete_existing=False):
    """Remove backend info for host name."""
    session = get_session()

    with session.begin():
        info_ref = _backend_info_query(session, context, host)
        if info_ref:
            if value:
                info_ref.update({"info_hash": value})
            elif delete_existing and info_ref['deleted'] != 1:
                info_ref.update({"deleted": 1,
                                 "deleted_at": timeutils.utcnow()})
        else:
            info_ref = models.BackendInfo()
            info_ref.update({"host": host,
                             "info_hash": value})
        info_ref.save(session)
        return info_ref


def _backend_info_query(session, context, host, read_deleted=False):
    result = model_query(
        context, models.BackendInfo, session=session,
        read_deleted=read_deleted,
    ).filter_by(
        host=host,
    ).first()

    return result
