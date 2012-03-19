import transaction
import argparse

from sqlalchemy import engine_from_config

from pyramid.paster import get_appsettings, setup_logging
from twofactor.models import DBSession, User
from twofactor.utils import get_barcode_image, generate_code


addparser = argparse.ArgumentParser(description='Add user')
addparser.add_argument('config', help='configuration file')
addparser.add_argument('--username', dest='username', help='username')


def add():
    arguments = addparser.parse_args()
    if not arguments.config or not arguments.username:
        addparser.print_usage()
    else:
        config_uri = arguments.config
        setup_logging(config_uri)
        settings = get_appsettings(config_uri)
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)
        with transaction.manager:
            secret = generate_code()
            username = arguments.username
            model = User(username=username, secret=secret)
            DBSession.add(model)
            print 'barcode url:', get_barcode_image(username, secret)
            print 'secret:', secret

removeparser = argparse.ArgumentParser(description='Remove user')
removeparser.add_argument('config', help='configuration file')
removeparser.add_argument('--username', dest='username', help='username')


def remove():
    arguments = removeparser.parse_args()
    if not arguments.config or not arguments.username:
        removeparser.print_usage()
    else:
        config_uri = arguments.config
        setup_logging(config_uri)
        settings = get_appsettings(config_uri)
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)
        with transaction.manager:
            user = DBSession.query(User).filter_by(
                username=arguments.username).all()
            if len(user) > 0:
                DBSession.delete(user[0])
            else:
                print '"%s" user not found' % arguments.username

listparser = argparse.ArgumentParser(description='Remove user')
listparser.add_argument('config', help='configuration file')


def listusers():
    arguments = removeparser.parse_args()
    if not arguments.config:
        removeparser.print_usage()
    else:
        config_uri = arguments.config
        setup_logging(config_uri)
        settings = get_appsettings(config_uri)
        engine = engine_from_config(settings, 'sqlalchemy.')
        DBSession.configure(bind=engine)
        with transaction.manager:
            for user in DBSession.query(User).all():
                print user.username
