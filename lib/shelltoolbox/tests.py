# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU General Public License version 3 (see the file LICENSE).

"""Tests for Python shell toolbox."""

__metaclass__ = type


import getpass
import os
from subprocess import CalledProcessError
import tempfile
import unittest

from shelltoolbox import (
    apt_get_install,
    cd,
    command,
    DictDiffer,
    environ,
    file_append,
    file_prepend,
    generate_ssh_keys,
    get_su_command,
    get_user_home,
    get_user_ids,
    join_command,
    mkdirs,
    run,
    search_file,
    Serializer,
    ssh,
    su,
    user_exists,
    )


class TestAptGetInstall(unittest.TestCase):

    packages = ('package1', 'package2')

    def _get_caller(self, **kwargs):
        def caller(*args):
            for k, v in kwargs.items():
                self.assertEqual(v, os.getenv(k))
        return caller

    def test_caller(self):
        # Ensure the correct command line is passed to caller.
        cmd = apt_get_install(*self.packages, caller=lambda *args: args)
        expected = ('apt-get', '-y', 'install') + self.packages
        self.assertTupleEqual(expected, cmd)

    def test_non_interactive_dpkg(self):
        # Ensure dpkg is called in non interactive mode.
        caller = self._get_caller(DEBIAN_FRONTEND='noninteractive')
        apt_get_install(*self.packages, caller=caller)

    def test_env_vars(self):
        # Ensure apt can be run using custom environment variables.
        caller = self._get_caller(DEBIAN_FRONTEND='noninteractive', LANG='C')
        apt_get_install(*self.packages, caller=caller, LANG='C')


class TestCdContextManager(unittest.TestCase):

    def test_cd(self):
        curdir = os.getcwd()
        self.assertNotEqual('/var', curdir)
        with cd('/var'):
            self.assertEqual('/var', os.getcwd())
        self.assertEqual(curdir, os.getcwd())


class TestCommand(unittest.TestCase):

    def testSimpleCommand(self):
        # Creating a simple command (ls) works and running the command
        # produces a string.
        ls = command('/bin/ls')
        self.assertIsInstance(ls(), str)

    def testArguments(self):
        # Arguments can be passed to commands.
        ls = command('/bin/ls')
        self.assertIn('Usage:', ls('--help'))

    def testMissingExecutable(self):
        # If the command does not exist, an OSError (No such file or
        # directory) is raised.
        bad = command('this command does not exist')
        with self.assertRaises(OSError) as info:
            bad()
        self.assertEqual(2, info.exception.errno)

    def testError(self):
        # If the command returns a non-zero exit code, an exception is raised.
        ls = command('/bin/ls')
        with self.assertRaises(CalledProcessError):
            ls('--not a valid switch')

    def testBakedInArguments(self):
        # Arguments can be passed when creating the command as well as when
        # executing it.
        ll = command('/bin/ls', '-al')
        self.assertIn('rw', ll()) # Assumes a file is r/w in the pwd.
        self.assertIn('Usage:', ll('--help'))

    def testQuoting(self):
        # There is no need to quote special shell characters in commands.
        ls = command('/bin/ls')
        ls('--help', '>')


class TestDictDiffer(unittest.TestCase):

    def testStr(self):
        a = dict(cow='moo', pig='oink')
        b = dict(cow='moo', pig='oinkoink', horse='nay')
        diff = DictDiffer(b, a)
        s = str(diff)
        self.assertIn("added: {'horse': None} -> {'horse': 'nay'}", s)
        self.assertIn("removed: {} -> {}", s)
        self.assertIn("changed: {'pig': 'oink'} -> {'pig': 'oinkoink'}", s)
        self.assertIn("unchanged: ['cow']", s)

    def testStrUnmodified(self):
        a = dict(cow='moo', pig='oink')
        diff = DictDiffer(a, a)
        s = str(diff)
        self.assertEquals('no changes', s)

    def testAddedOrChanged(self):
        a = dict(cow='moo', pig='oink')
        b = dict(cow='moo', pig='oinkoink', horse='nay')
        diff = DictDiffer(b, a)
        expected = set(['horse', 'pig'])
        self.assertEquals(expected, diff.added_or_changed)


class TestEnviron(unittest.TestCase):

    def test_existing(self):
        # If an existing environment variable is changed, it is
        # restored during context cleanup.
        os.environ['MY_VARIABLE'] = 'foo'
        with environ(MY_VARIABLE='bar'):
            self.assertEqual('bar', os.getenv('MY_VARIABLE'))
        self.assertEqual('foo', os.getenv('MY_VARIABLE'))
        del os.environ['MY_VARIABLE']

    def test_new(self):
        # If a new environment variable is added, it is removed during
        # context cleanup.
        with environ(MY_VAR1='foo', MY_VAR2='bar'):
            self.assertEqual('foo', os.getenv('MY_VAR1'))
            self.assertEqual('bar', os.getenv('MY_VAR2'))
        self.assertIsNone(os.getenv('MY_VAR1'))
        self.assertIsNone(os.getenv('MY_VAR2'))


class BaseCreateFile(object):

    def create_file(self, content):
        f = tempfile.NamedTemporaryFile('w', delete=False)
        f.write(content)
        f.close()
        return f


class BaseTestFile(BaseCreateFile):

    base_content = 'line1\n'
    new_content = 'new line\n'

    def check_file_content(self, content, filename):
        self.assertEqual(content, open(filename).read())


class TestFileAppend(unittest.TestCase, BaseTestFile):

    def test_append(self):
        # Ensure the new line is correctly added at the end of the file.
        f = self.create_file(self.base_content)
        file_append(f.name, self.new_content)
        self.check_file_content(self.base_content + self.new_content, f.name)

    def test_existing_content(self):
        # Ensure nothing happens if the file already contains the given line.
        content = self.base_content + self.new_content
        f = self.create_file(content)
        file_append(f.name, self.new_content)
        self.check_file_content(content, f.name)

    def test_new_line_in_file_contents(self):
        # A new line is automatically added before the given content if it
        # is not present at the end of current file.
        f = self.create_file(self.base_content.strip())
        file_append(f.name, self.new_content)
        self.check_file_content(self.base_content + self.new_content, f.name)

    def test_new_line_in_given_line(self):
        # A new line is automatically added to the given line if not present.
        f = self.create_file(self.base_content)
        file_append(f.name, self.new_content.strip())
        self.check_file_content(self.base_content + self.new_content, f.name)

    def test_non_existent_file(self):
        # Ensure the file is created if it does not exist.
        filename = tempfile.mktemp()
        file_append(filename, self.base_content)
        self.check_file_content(self.base_content, filename)

    def test_fragment(self):
        # Ensure a line fragment is not matched.
        f = self.create_file(self.base_content)
        fragment = self.base_content[2:]
        file_append(f.name, fragment)
        self.check_file_content(self.base_content + fragment, f.name)


class TestFilePrepend(unittest.TestCase, BaseTestFile):

    def test_prpend(self):
        # Ensure the new content is correctly prepended at the beginning of
        # the file.
        f = self.create_file(self.base_content)
        file_prepend(f.name, self.new_content)
        self.check_file_content(self.new_content + self.base_content, f.name)

    def test_existing_content(self):
        # Ensure nothing happens if the file already starts with the given
        # content.
        content = self.base_content + self.new_content
        f = self.create_file(content)
        file_prepend(f.name, self.base_content)
        self.check_file_content(content, f.name)

    def test_move_content(self):
        # If the file contains the given content, but not at the beginning,
        # the content is moved on top.
        f = self.create_file(self.base_content + self.new_content)
        file_prepend(f.name, self.new_content)
        self.check_file_content(self.new_content + self.base_content, f.name)

    def test_new_line_in_given_line(self):
        # A new line is automatically added to the given line if not present.
        f = self.create_file(self.base_content)
        file_prepend(f.name, self.new_content.strip())
        self.check_file_content(self.new_content + self.base_content, f.name)


class TestGenerateSSHKeys(unittest.TestCase):

    def test_generation(self):
        # Ensure ssh keys are correctly generated.
        filename = tempfile.mktemp()
        generate_ssh_keys(filename)
        first_line = open(filename).readlines()[0].strip()
        self.assertEqual('-----BEGIN RSA PRIVATE KEY-----', first_line)
        pub_content = open(filename + '.pub').read()
        self.assertTrue(pub_content.startswith('ssh-rsa'))


class TestGetSuCommand(unittest.TestCase):

    def test_current_user(self):
        # If the su is requested as current user, the arguments are
        # returned as given.
        cmd = ('ls', '-l')
        command = get_su_command(getpass.getuser(), cmd)
        self.assertSequenceEqual(cmd, command)

    def test_another_user(self):
        # Ensure "su" is prepended and arguments are correctly quoted.
        command = get_su_command('nobody', ('ls', '-l', 'my file'))
        self.assertSequenceEqual(
            ('su', 'nobody', '-c', "ls -l 'my file'"), command)


class TestGetUserHome(unittest.TestCase):

    def test_existent(self):
        # Ensure the real home directory is returned for existing users.
        self.assertEqual('/root', get_user_home('root'))

    def test_non_existent(self):
        # If the user does not exist, return a default /home/[username] home.
        user = '_this_user_does_not_exist_'
        self.assertEqual('/home/' + user, get_user_home(user))


class TestGetUserIds(unittest.TestCase):

    def test_get_user_ids(self):
        # Ensure the correct uid and gid are returned.
        uid, gid = get_user_ids('root')
        self.assertEqual(0, uid)
        self.assertEqual(0, gid)


class TestJoinCommand(unittest.TestCase):

    def test_normal(self):
        # Ensure a normal command is correctly parsed.
        command = 'ls -l'
        self.assertEqual(command, join_command(command.split()))

    def test_containing_spaces(self):
        # Ensure args containing spaces are correctly quoted.
        args = ('command', 'arg containig spaces')
        self.assertEqual("command 'arg containig spaces'", join_command(args))

    def test_empty(self):
        # Ensure empty args are correctly quoted.
        args = ('command', '')
        self.assertEqual("command ''", join_command(args))


class TestMkdirs(unittest.TestCase):

    def test_intermediate_dirs(self):
        # Ensure the leaf directory and all intermediate ones are created.
        base_dir = tempfile.mktemp(suffix='/')
        dir1 = tempfile.mktemp(prefix=base_dir)
        dir2 = tempfile.mktemp(prefix=base_dir)
        mkdirs(dir1, dir2)
        self.assertTrue(os.path.isdir(dir1))
        self.assertTrue(os.path.isdir(dir2))

    def test_existing_dir(self):
        # If the leaf directory already exists the function returns
        # without errors.
        mkdirs('/tmp')

    def test_existing_file(self):
        # An `OSError` is raised if the leaf path exists and it is a file.
        f = tempfile.NamedTemporaryFile('w', delete=False)
        f.close()
        with self.assertRaises(OSError):
            mkdirs(f.name)


class TestRun(unittest.TestCase):

    def testSimpleCommand(self):
        # Running a simple command (ls) works and running the command
        # produces a string.
        self.assertIsInstance(run('/bin/ls'), str)

    def testStdoutReturned(self):
        # Running a simple command (ls) works and running the command
        # produces a string.
        self.assertIn('Usage:', run('/bin/ls', '--help'))

    def testCalledProcessErrorRaised(self):
        # If an error occurs a CalledProcessError is raised with the return
        # code, command executed, and the output of the command.
        with self.assertRaises(CalledProcessError) as info:
            run('ls', '--not a valid switch')
        exception = info.exception
        self.assertEqual(2, exception.returncode)
        self.assertEqual("['ls', '--not a valid switch']", exception.cmd)
        self.assertIn('unrecognized option', exception.output)

    def testErrorRaisedStdoutNotRedirected(self):
        with self.assertRaises(CalledProcessError):
            run('ls', '--not a valid switch', stdout=None)

    def testNoneArguments(self):
        # Ensure None is ignored when passed as positional argument.
        self.assertIn('Usage:', run('/bin/ls', None, '--help', None))


class TestSearchFile(unittest.TestCase, BaseCreateFile):

    content1 = 'content1\n'
    content2 = 'content2\n'

    def setUp(self):
        self.filename = self.create_file(self.content1 + self.content2).name

    def tearDown(self):
        os.remove(self.filename)

    def test_grep(self):
        # Ensure plain text is correctly matched.
        self.assertEqual(self.content2, search_file('ent2', self.filename))
        self.assertEqual(self.content1, search_file('content', self.filename))

    def test_no_match(self):
        # Ensure the function does not return false positives.
        self.assertIsNone(search_file('no_match', self.filename))

    def test_regexp(self):
        # Ensure the function works with regular expressions.
        self.assertEqual(self.content2, search_file('\w2', self.filename))


class TestSerializer(unittest.TestCase):

    def setUp(self):
        self.path = tempfile.mktemp()
        self.data = {'key': 'value'}

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_serializer(self):
        # Ensure data is correctly serializied and deserialized.
        s = Serializer(self.path)
        s.set(self.data)
        self.assertEqual(self.data, s.get())

    def test_existence(self):
        # Ensure the file is created only when needed.
        s = Serializer(self.path)
        self.assertFalse(s.exists())
        s.set(self.data)
        self.assertTrue(s.exists())

    def test_default_value(self):
        # If the file does not exist, the serializer returns a default value.
        s = Serializer(self.path)
        self.assertEqual({}, s.get())
        s = Serializer(self.path, default=47)
        self.assertEqual(47, s.get())

    def test_another_serializer(self):
        # It is possible to use a custom serializer (e.g. pickle).
        import pickle
        s = Serializer(
            self.path, serialize=pickle.dump, deserialize=pickle.load)
        s.set(self.data)
        self.assertEqual(self.data, s.get())


class TestSSH(unittest.TestCase):

    def setUp(self):
        self.last_command = None

    def remove_command_options(self, cmd):
        cmd = list(cmd)
        del cmd[1:7]
        return cmd

    def caller(self, cmd):
        self.last_command = self.remove_command_options(cmd)

    def check_last_command(self, expected):
        self.assertSequenceEqual(expected, self.last_command)

    def test_current_user(self):
        # Ensure ssh command is correctly generated for current user.
        sshcall = ssh('example.com', caller=self.caller)
        sshcall('ls -l')
        self.check_last_command(['ssh', 'example.com', '--', 'ls -l'])

    def test_another_user(self):
        # Ensure ssh command is correctly generated for a different user.
        sshcall = ssh('example.com', 'myuser', caller=self.caller)
        sshcall('ls -l')
        self.check_last_command(['ssh', 'myuser@example.com', '--', 'ls -l'])

    def test_ssh_key(self):
        # The ssh key path can be optionally provided.
        sshcall = ssh('example.com', key='/tmp/foo', caller=self.caller)
        sshcall('ls -l')
        self.check_last_command([
            'ssh', '-i', '/tmp/foo', 'example.com', '--', 'ls -l'])

    def test_error(self):
        # If the ssh command exits with an error code, a
        # `subprocess.CalledProcessError` is raised.
        sshcall = ssh('example.com', caller=lambda cmd: 1)
        with self.assertRaises(CalledProcessError):
            sshcall('ls -l')

    def test_ignore_errors(self):
        # If ignore_errors is set to True when executing the command, no error
        # will be raised, even if the command itself returns an error code.
        sshcall = ssh('example.com', caller=lambda cmd: 1)
        sshcall('ls -l', ignore_errors=True)


current_euid = os.geteuid()
current_egid = os.getegid()
current_home = os.environ['HOME']
example_euid = current_euid + 1
example_egid = current_egid + 1
example_home = '/var/lib/example'
userinfo = {'example_user': dict(
        ids=(example_euid, example_egid), home=example_home)}
effective_values = dict(uid=current_euid, gid=current_egid)


def stub_os_seteuid(value):
    effective_values['uid'] = value


def stub_os_setegid(value):
    effective_values['gid'] = value


class TestSuContextManager(unittest.TestCase):

    def setUp(self):
        import shelltoolbox
        self.os_seteuid = os.seteuid
        self.os_setegid = os.setegid
        self.shelltoolbox_get_user_ids = shelltoolbox.get_user_ids
        self.shelltoolbox_get_user_home = shelltoolbox.get_user_home
        os.seteuid = stub_os_seteuid
        os.setegid = stub_os_setegid
        shelltoolbox.get_user_ids = lambda user: userinfo[user]['ids']
        shelltoolbox.get_user_home = lambda user: userinfo[user]['home']

    def tearDown(self):
        import shelltoolbox
        os.seteuid = self.os_seteuid
        os.setegid = self.os_setegid
        shelltoolbox.get_user_ids = self.shelltoolbox_get_user_ids
        shelltoolbox.get_user_home = self.shelltoolbox_get_user_home

    def testChange(self):
        with su('example_user'):
            self.assertEqual(example_euid, effective_values['uid'])
            self.assertEqual(example_egid, effective_values['gid'])
            self.assertEqual(example_home, os.environ['HOME'])

    def testEnvironment(self):
        with su('example_user') as e:
            self.assertEqual(example_euid, e.uid)
            self.assertEqual(example_egid, e.gid)
            self.assertEqual(example_home, e.home)

    def testRevert(self):
        with su('example_user'):
            pass
        self.assertEqual(current_euid, effective_values['uid'])
        self.assertEqual(current_egid, effective_values['gid'])
        self.assertEqual(current_home, os.environ['HOME'])

    def testRevertAfterFailure(self):
        try:
            with su('example_user'):
                raise RuntimeError()
        except RuntimeError:
            self.assertEqual(current_euid, effective_values['uid'])
            self.assertEqual(current_egid, effective_values['gid'])
            self.assertEqual(current_home, os.environ['HOME'])


class TestUserExists(unittest.TestCase):

    def test_user_exists(self):
        self.assertTrue(user_exists('root'))
        self.assertFalse(user_exists('_this_user_does_not_exist_'))


if __name__ == '__main__':
    unittest.main()
