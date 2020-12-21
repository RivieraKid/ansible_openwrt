#!/usr/bin/python
'''
This is a module docstring
'''

from pathlib import Path
import paramiko
import netifaces
from ansible.module_utils.basic import AnsibleModule

# Globals
package_to_install = None
router = None
user = None
state = None
ssh_identity = None
check_mode = False
changed = False
update = True
debug = False


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
    if ssh_identity is not None:
        print("SSH_IDENTITY = {}".format(ssh_identity))
        ssh_key = paramiko.RSAKey.from_private_key_file(ssh_identity)
    else:
        keyfile = '{}/.ssh/id_rsa'.format(str(Path.home()))
        ssh_key = paramiko.RSAKey.from_private_key_file(keyfile)
    return ssh_key

def run_command_on_router(command):
    '''
    This is a function docstring
    '''

    global router

    ssh_key = get_ssh_key()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname=router, username=user, pkey=ssh_key)

    _, ssh_stdout, ssh_stderr = ssh.exec_command(command)

    ssh_stdout_lines = ssh_stdout.read().decode('ascii').split('\n')
    ssh_stderr_lines = ssh_stderr.read().decode('ascii').split('\n')

    return (ssh_stdout_lines, ssh_stderr_lines)

def get_package_version():
    '''
    This is a function docstring
    '''

    cmd_to_execute = 'opkg status {}'.format(package_to_install)
    stdout, _ = run_command_on_router(cmd_to_execute)

    for line in stdout:
        if line.startswith('Version: '):
            return line.split(' ')[1]
    return None

def main():
    '''
    This is a function docstring
    '''

    global package_to_install
    global router
    global user
    global state
    global ssh_identity
    global check_mode
    global changed
    global update
    global debug
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
    package_to_install = module.params['pkg']
    router = get_router(module.params['router'])
    user = module.params['user']
    state = module.params['state']
    ssh_identity = module.params['ssh_identity']
    check_mode = module.check_mode
    changed = False
    update = module.params['refresh']
    debug = module.params['debug']

    response = {}

    if debug:
        response['module.params'] = module.params

    if update:
        cmd_to_execute = 'opkg update'
        stdout, _ = run_command_on_router(cmd_to_execute)

    if (state == 'present'):
        if not check_mode:
            # We're not in check mode, so need to actually do it
            cmd_to_execute = 'opkg install {}'.format(package_to_install)
            stdout, _ = run_command_on_router(cmd_to_execute)
            response['reason'] = 'Requested state was {} and {} was either not installed or had an update'.format(
                state, package_to_install)
            response['stdout_lines'] = stdout
            changed = True
        else:
            response['reason'] = 'Requested state was {} and {} was either not installed or had an update, but wasn\'t installed because check mode is enabled'.format(
                state, package_to_install)
    else:
        # State should be absent, so check if the package is installed and remove it
        if not check_mode:
            # The package is installed
            cmd_to_execute = 'opkg remove {}'.format(package_to_install)
            stdout, _ = run_command_on_router(cmd_to_execute)
            response['reason'] = 'Requested state was {}, so {} was removed'.format(
                state, package_to_install)
            response['stdout_lines'] = stdout
            if stdout[0].startswith('Refusing to remove essential package'):
                module.fail_json(msg=stdout[0], meta=response)
            changed = True
            if stdout[0] == "No packages removed.":
                response['reason'] = 'Requested state was {}, but {} wasn\'t installed so no action was taken'.format(
                    state, package_to_install)
                changed = False
        else:
            response['reason'] = 'Requested state was {}, but check mode is enabled so {} was not removed'.format(
                state, package_to_install)

    module.exit_json(changed=changed, meta=response)


if __name__ == '__main__':
    main()
