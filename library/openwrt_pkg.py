#!/usr/bin/python
'''
This is a module docstring
'''

from pathlib import Path
import paramiko
import netifaces
from ansible.module_utils.basic import AnsibleModule

# Globals
PACKAGE_TO_INSTALL = None
ROUTER = None
USER = None
STATE = None
SSH_IDENTITY = None
CHECK_MODE = False
changed = False
UPDATE = True
DEBUG = False
response = {}


def get_router(router):
    '''
    This is a function docstring
    '''

    if router is None:
        gws = netifaces.gateways()
        return gws['default'][netifaces.AF_INET][0]
    return router

def get_ssh_key():
    '''
    This is a function docstring
    '''

    ssh_key = ''
    if SSH_IDENTITY is not None:
        print("SSH_IDENTITY = {}".format(SSH_IDENTITY))
        ssh_key = paramiko.RSAKey.from_private_key_file(SSH_IDENTITY)
    else:
        keyfile = '{}/.ssh/id_rsa'.format(str(Path.home()))
        ssh_key = paramiko.RSAKey.from_private_key_file(keyfile)
    return ssh_key

def run_command_on_router(command):
    '''
    This is a function docstring
    '''

    global ROUTER

    ssh_key = get_ssh_key()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=ROUTER, username=USER, pkey=ssh_key)

    _, ssh_stdout, ssh_stderr = ssh.exec_command(command)

    ssh_stdout_lines = ssh_stdout.read().decode('ascii').split('\n')
    ssh_stderr_lines = ssh_stderr.read().decode('ascii').split('\n')

    return (ssh_stdout_lines, ssh_stderr_lines)

def get_package_version():
    '''
    This is a function docstring
    '''

    cmd_to_execute = 'opkg status {}'.format(PACKAGE_TO_INSTALL)
    stdout, _ = run_command_on_router(cmd_to_execute)

    for line in stdout:
        if line.startswith('Version: '):
            return line.split(' ')[1]
    return None

def add_standard_debug_response(params):
    if DEBUG:
        response['module.params'] = params

def update_package_list():
    if UPDATE:
        cmd_to_execute = 'opkg update'
        _, _ = run_command_on_router(cmd_to_execute)

def main():
    '''
    This is a function docstring
    '''

    global PACKAGE_TO_INSTALL
    global ROUTER
    global USER
    global STATE
    global SSH_IDENTITY
    global CHECK_MODE
    global changed
    global UPDATE
    global DEBUG
    global response

    module = AnsibleModule(
        argument_spec={
            "pkg":          {"required": True, "type": "str"},
            "router":       {"required": False, "type": "str"},
            "user":         {"required": False, "default": "root", "type": "str"},
            "state":        {"default": "present", "choices": ['present',
                                                               'absent'], "type": 'str'},
            "version":      {"required": False, "type": "str"},
            "ssh_identity": {"required": False, "type": "str"},
            "refresh":      {"default": "False", "type": "str" },
            "debug":        {"default": "False", "type": "str" }
        },
        supports_check_mode=True
    )

    # Parse the parameters, to make the code more readable
    PACKAGE_TO_INSTALL = module.params['pkg']
    ROUTER = get_router(module.params['router'])
    USER = module.params['user']
    STATE = module.params['state']
    SSH_IDENTITY = module.params['ssh_identity']
    CHECK_MODE = module.check_mode
    changed = False
    UPDATE = module.params['refresh']
    DEBUG = module.params['debug']

    response = {}

    add_standard_debug_response(module.params)

    update_package_list()

    if STATE == 'present':
        if not CHECK_MODE:
            # We're not in check mode, so need to actually do it
            cmd_to_execute = 'opkg install {}'.format(PACKAGE_TO_INSTALL)
            stdout, _ = run_command_on_router(cmd_to_execute)
            response['reason'] = \
                'Requested state was {} and {} was either not installed or had an update' \
                .format(STATE, PACKAGE_TO_INSTALL)
            response['stdout_lines'] = stdout
            changed = True
        else:
            response['reason'] = \
                'Requested state was {} and {} was either not installed or had an update, but \
                    wasn\'t installed because check mode is enabled'.format(
                STATE, PACKAGE_TO_INSTALL)
    else:
        # State should be absent, so check if the package is installed and remove it
        if not CHECK_MODE:
            # The package is installed
            cmd_to_execute = 'opkg remove {}'.format(PACKAGE_TO_INSTALL)
            stdout, _ = run_command_on_router(cmd_to_execute)
            response['reason'] = 'Requested state was {}, so {} was removed'.format(
                STATE, PACKAGE_TO_INSTALL)
            response['stdout_lines'] = stdout
            if stdout[0].startswith('Refusing to remove essential package'):
                module.fail_json(msg=stdout[0], meta=response)
            changed = True
            if stdout[0] == "No packages removed.":
                response['reason'] = \
                    'Requested state was {}, but {} wasn\'t installed so no action was taken'\
                        .format(STATE, PACKAGE_TO_INSTALL)
                changed = False
        else:
            response['reason'] = \
                'Requested state was {}, but check mode is enabled so {} was not removed'.format(
                STATE, PACKAGE_TO_INSTALL)

    module.exit_json(changed=changed, meta=response)


if __name__ == '__main__':
    main()
