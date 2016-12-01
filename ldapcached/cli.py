# -*- coding: utf-8 -*-

from __future__ import absolute_import

import logging
import os
import sys
import traceback

import click

import yaml

import ldapcached.daemon


# Logger.
_log = None


# TODO: Integrate with twisted.python.log.
def _configure_logger(**kwargs):
    """
    Configure root logger.

    :param kwargs: Arguments for logging.basicConfig().
    :return: None.
    """

    root_logger = logging.getLogger()
    list(map(root_logger.removeHandler, root_logger.handlers[:]))
    list(map(root_logger.removeFilter, root_logger.filters[:]))
    logging.basicConfig(
        format=' %(levelname).1s|%(asctime)s|%(process)d:%(thread)d| '
               '%(message)s',
        **kwargs)
    global _log
    _log = logging.getLogger()


def _get_log_level(level_str):
    return {
        'D': logging.DEBUG,
        'I': logging.INFO,
        'W': logging.WARNING,
        'E': logging.ERROR,
        'C': logging.CRITICAL,
    }[level_str.upper()[0]]


def _configure_basic_logger(level_str='I'):
    """
    Configure root logger.

    :param level_str: Log level string.
    :return: None.
    """

    _configure_logger(
        stream=sys.stderr,
        level=_get_log_level(level_str))


def _configure_file_logger(log_file_path, level_str='I'):
    _configure_logger(
        filename=log_file_path,
        level=_get_log_level(level_str))


@click.command(context_settings={'help_option_names': ['-h', '--help']})
@click.option('--quiet', '-q',
              is_flag=True)
@click.option('--log-level', '-l',
              default='info')
@click.option('--log-file', '-L',
              default='')
@click.option('--conf-file', '-c',
              required=True)
def _main(quiet, log_level, log_file, conf_file):
    if quiet:
        log_level = 'error'

    if log_file:
        _configure_file_logger(log_file, log_level)
    else:
        _configure_basic_logger(log_level)

    with open(conf_file) as conf_file_obj:
        conf = yaml.safe_load(conf_file_obj)
    ldapcached.daemon.run(conf)


def main():
    _configure_basic_logger()

    try:
        _main()
    except SystemExit:
        raise
    except BaseException as exc:
        logging.error('v' * 40)
        logging.error('%s', str(exc))
        for line in traceback.format_exc().rstrip().split('\n'):
            logging.error('%s', line)
        logging.error('^' * 40)
        return os.EX_SOFTWARE


if __name__ == "__main__":
    main()
