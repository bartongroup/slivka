from collections import OrderedDict

from nose.tools import assert_list_equal

from tests.runner.stubs import RunnerStub, runner_factory


def test_arguments_passed():
    args = ['first', 'containing space', 'sp3c][a| (h*rac7er$', 'last']
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {},
        'arguments': args.copy(),
        'outputs': {}
    })
    assert_list_equal(runner.get_args({}), args)


def test_number_option():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'myoption': {'arg': '-n $(value)', 'type': 'number'}
        },
        'outputs': {}
    })
    assert_list_equal(runner.get_args({}), [])
    assert_list_equal(runner.get_args({'myoption': 3.1415}), ['-n', '3.1415'])
    assert_list_equal(runner.get_args({'myoption': '5.24'}), ['-n', '5.24'])
    assert_list_equal(runner.get_args({'myoption': 0}), ['-n', '0'])
    assert_list_equal(runner.get_args({'myoption': '0'}), ['-n', '0'])
    assert_list_equal(runner.get_args({'myoption': False}), [])


def test_symbol_delimited_option():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'myoption': {'arg': '--option=$(value)'}
        },
        'outputs': {}
    })
    assert_list_equal(runner.get_args({}), [])
    assert_list_equal(runner.get_args({'myoption': None}), [])
    assert_list_equal(runner.get_args({'myoption': ''}), ['--option='])
    assert_list_equal(
        runner.get_args({'myoption': 'my value'}),
        ['--option=my value']
    )


def test_space_delimited_option():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'myoption': {'arg': '--option $(value)'}
        },
        'outputs': {}
    })
    assert_list_equal(
        runner.get_args({'myoption': 'value'}),
        ['--option', 'value']
    )
    assert_list_equal(
        runner.get_args({'myoption': 'my value'}),
        ['--option', 'my value']
    )
    assert_list_equal(
        runner.get_args({'myoption': 'my \'fun \' value'}),
        ['--option', 'my \'fun \' value']
    )


def test_quoted_option():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'myoption': {'arg': '\'--option $(value)\''},
            'otheropt': {'arg': '"--option $(value)"'}
        },
        'outputs': {}
    })
    assert_list_equal(
        runner.get_args({'myoption': 'value'}),
        ['--option value']
    )
    assert_list_equal(
        runner.get_args({'myoption': 'my value'}),
        ['--option my value']
    )
    assert_list_equal(
        runner.get_args({'otheropt': 'my value'}),
        ['--option my value']
    )

    assert_list_equal(
        runner.get_args({'myoption': 'my \'fun \' value'}),
        ['--option my \'fun \' value']
    )
    assert_list_equal(
        runner.get_args({'otheropt': 'my \'fun \' value'}),
        ['--option my \'fun \' value']
    )


def test_flag_option():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'myflag': {'arg': '--flag', 'type': 'flag'}
        },
        'outputs': {}
    })
    assert_list_equal(runner.get_args({}), [])
    assert_list_equal(runner.get_args({'myflag': False}), [])
    assert_list_equal(runner.get_args({'myflag': None}), [])
    assert_list_equal(runner.get_args({'myflag': True}), ['--flag'])


def test_default_substitution():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'input': {
                'arg': '-v=$(value)',
                'value': 'default'
            }
        },
        'outputs': {}
    })
    assert_list_equal(runner.get_args({'input': 'foo'}), ['-v=foo'])
    assert_list_equal(runner.get_args({'input': None}), ['-v=default'])
    assert_list_equal(runner.get_args({'input': ''}), ['-v='])
    assert_list_equal(runner.get_args({}), ['-v=default'])


def test_parameters_ordering():
    runner = RunnerStub({
        "baseCommand": [],
        "inputs": OrderedDict([
            ('iters', {
                'arg': '--iter=$(value)',
                'type': 'number'
            }),
            ('outfile', {
                'arg': '-o $(value)',
                'type': 'file'
            }),
            ('verbose', {
                'arg':  '-V',
                'type': 'flag'
            }),
            ('infile', {
                'arg': '$(value)'
            })
        ]),
        "arguments": [],
        "outputs": {},
        "env": {}
    })

    assert_list_equal(runner.get_args({}), [])

    inputs = {
        'iters': 5,
        'outfile': 'output.txt',
        'verbose': True,
        'infile': 'input.txt'
    }
    assert_list_equal(
        runner.get_args(inputs),
        ['--iter=5', '-o', 'output.txt', '-V', 'input.txt']
    )

    inputs = {
        'iters': 3,
        'verbose': False,
        'infile': 'input.txt'
    }
    assert_list_equal(runner.get_args(inputs), ['--iter=3', 'input.txt'])

    inputs = {
        'outfile': 'out.out',
        'verbose': True,
        'iters': 10
    }
    assert_list_equal(
        runner.get_args(inputs),
        ['--iter=10', '-o', 'out.out', '-V']
    )


def test_file_input():
    runner = RunnerStub({
        'baseCommand': [],
        'inputs': {
            'input': {
                'arg': '$(value)',
                'type': 'file',
                'symlink': 'input.in'
            }
        },
        'outputs': {}
    })
    assert_list_equal(runner.get_args({'input': 'myfile'}), ['input.in'])
    assert_list_equal(runner.get_args({'input': None}), [])
    assert_list_equal(runner.get_args({}), [])


def test_repeated_array_input():
    runner = runner_factory(inputs={
        'array': {
            'arg': '-m=$(value)',
            'type': 'array'
        }
    })
    assert_list_equal(
        runner.get_args({'array': ['a', 'b', 'c', 'd']}),
        ['-m=a', '-m=b', '-m=c', '-m=d']
    )
    assert_list_equal(runner.get_args({'array': []}), [])


def test_joined_array_input():
    runner = runner_factory(inputs={
        'array': {
            'arg': '-m=$(value)',
            'type': 'array',
            'join': ','
        }
    })
    assert_list_equal(runner.get_args({'array': ['a', 'b', 'c']}), ['-m=a,b,c'])
