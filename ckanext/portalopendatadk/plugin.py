import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import string
from ckan.lib.navl.dictization_functions import Missing
from ckan.logic.schema import default_user_schema, default_update_user_schema
from ckan.logic.action.create import user_create as core_user_create
from ckan.logic.action.update import user_update as core_user_update
from ckan.lib import mailer
from pylons import config
from ckan import authz
_ = toolkit._



def latest_datasets():
    '''Return a sorted list of the latest datasets.'''

    datasets = toolkit.get_action('package_search')(
        data_dict={'rows': 10, 'sort': 'metadata_created desc' })

    return datasets['results']


def most_popular_datasets():
    '''Return a sorted list of the most popular datasets.'''

    datasets = toolkit.get_action('package_search')(
        data_dict={'rows': 10, 'sort': 'views_recent desc' })

    return datasets['results']


class PortalOpenDataDKPlugin(plugins.SingletonPlugin):
    '''portal.opendata.dk theme plugin.

    '''
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IActions)

    def update_config(self, config):
        toolkit.add_template_directory(config, 'templates')
        toolkit.add_public_directory(config, 'public')
        toolkit.add_resource('fanstatic', 'portalopendatadk')

    def get_helpers(self):
        return {'portalopendatadk_latest_datasets': latest_datasets,
                'portalopendatadk_most_popular_datasets': most_popular_datasets}
    
    def get_actions(self):

        return {
            'user_create': custom_user_create,
            'user_update': custom_user_update,
            'send_password_notice_email': send_password_notice_email
        }

# Custom actions

def custom_user_create(context, data_dict):

    context['schema'] = custom_create_user_schema(
        form_schema='password1' in context.get('schema', {}))

    return core_user_create(context, data_dict)


def custom_user_update(context, data_dict):

    context['schema'] = custom_update_user_schema(
        form_schema='password1' in context.get('schema', {}))

    return core_user_update(context, data_dict)


# Custom schemas

def custom_create_user_schema(form_schema=False):

    schema = default_user_schema()

    schema['password'] = [custom_user_password_validator,
                          toolkit.get_validator('user_password_not_empty'),
                          toolkit.get_validator('ignore_missing'),
                          unicode]

    if form_schema:
        schema['password1'] = [toolkit.get_validator('user_both_passwords_entered'),
                               custom_user_password_validator,
                               toolkit.get_validator('user_passwords_match'),
                               unicode]
        schema['password2'] = [unicode]

    return schema


def custom_update_user_schema(form_schema=False):

    schema = default_update_user_schema()

    schema['password'] = [custom_user_password_validator,
                          toolkit.get_validator('user_password_not_empty'),
                          toolkit.get_validator('ignore_missing'),
                          unicode]

    if form_schema:
        schema['password'] = [toolkit.get_validator('ignore_missing')]
        schema['password1'] = [toolkit.get_validator('ignore_missing'),
                               custom_user_password_validator,
                               toolkit.get_validator('user_passwords_match'),
                               unicode]
        schema['password2'] = [toolkit.get_validator('ignore_missing'),
                               unicode]

    return schema


# Custom validators
WRONG_PASSWORD_MESSAGE = ('Your password must be 8 characters or longer, ' +
                          'contain at least one capital letter, one small letter, ' +
                          'one number(0-9) and a ' +
                          'special_character(!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~)')


def custom_user_password_validator(key, data, errors, context):
    value = data[key]
    special_chars = string.punctuation

    if isinstance(value, Missing):
        pass
    elif not isinstance(value, basestring):
        errors[('password',)].append(_('Passwords must be strings'))
    elif value == '':
        pass
    elif (len(value) < 8 or
          not any(x.isdigit() for x in value) or
          not any(x.isupper() for x in value) or
          not any(x.islower() for x in value) or
          not any(x in special_chars for x in value)
          ):
        errors[('password',)].append(_(WRONG_PASSWORD_MESSAGE))

@toolkit.side_effect_free
def send_password_notice_email(context, data_dict):
    '''Sends an email to all the users according to new rules'''

    if not authz.is_sysadmin(toolkit.c.user):
        toolkit.abort(403, _('You are not authorized to access this list'))

    user_list = toolkit.get_action('user_list')(context, data_dict)
    update_password_email = \
            'Hello {},\n\nWe are improving our user login password security according \
to the industry standards. Please update your current account password \
according to the new password criteria stated below. \n\n\
- Your new password should be of minimum 8 characters or longer\n\
- Should have at least one of each\n\
  - capital letter\n\
  - one small letter\n\
  - one number(0-9)\n\
  - one special character\n\
For example, the structure of the password should be similar to this \
"Capsmall12!@".\n\n\
Make sure to update your password before {}. After {}, you would not \
be able to login using your old password (which does not meet the \
criteria stated above).\n\n\
Have a great day.\n\n\
---\n\n\
Message sent by Open Data DK -  (https://admin.opendata.dk)'

    for user in user_list:
        
        email = user['email']
        
        if email:
            mailer.mail_recipient(
                    user['name'], email,
                    'Login security update for Open Data DK portal',
                    update_password_email.format(user['display_name'],
                    config.get('ckan.pass_date','24th June 2020'),
                    config.get('ckan.pass_date','24th June 2020')))
    return u'Email Sent Successfully'