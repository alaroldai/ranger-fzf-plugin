#!/usr/bin/env python3 -O
from ranger.api.commands import Command
import subprocess, os
import json
from pathlib import Path, PurePath
from re import sub
import sys
from functools import lru_cache

def get_watchman_root():
  wm = subprocess.run(['watchman', 'watch-list'], stdout=subprocess.PIPE, universal_newlines=True)
  js = json.loads(wm.stdout.strip())
  parents = set(PurePath(Path.cwd()).parents)
  for w in [PurePath(p) for p in js['roots']]:
    if w in parents:
      return w.as_posix()
  return None

@lru_cache()
def find_files(working_directory, quantifier):
    print('Running find_files in %s' % working_directory)
    wmroot = get_watchman_root()
    if wmroot:
      relroot = PurePath(working_directory).relative_to(PurePath(wmroot)).as_posix()
      wmquery = json.dumps([
        'query',
        wmroot,
        {
          # 'relative_root': relroot,
          'fields': ['name'],
          'expression': [
            'allof',
            ['type', 'f'],
            ['anyof'] + [['suffix', sfx] for sfx in [
              '',
              'bzl',
              'c',
              'cc',
              'cconf',
              'cpp',
              'css',
              'h',
              'hh',
              'hs',
              'html',
              'java',
              'json',
              'm',
              'mm',
              'mustache',
              'php',
              'plist',
              'py',
              'rs',
              'swift',
              'toml',
              'ts',
              'xml',
            ]]
          ]
        }
      ])
      watchman = subprocess.Popen([
        'watchman',
        '-j',
      ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)
      stdout, stderr = watchman.communicate(wmquery)
      return wmroot, bytes('\n'.join(json.loads(stdout)['files']), encoding='utf-8')
    else:
      shell = subprocess.Popen(['bash'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
      command = ' '.join([
        "find -L {} \( -path '*/\.*' -o -fstype 'dev' -o -fstype 'proc' \) -prune -o".format(working_directory),
        "-type d" if quantifier else "",
        "-print 2> /dev/null | sed 1d" # | cut -b3-"
      ])
      stdout, stderr = shell.communicate(bytes(command, encoding='utf-8'))
      if stderr:
        print(stderr)
      return '', stdout

# https://github.com/ranger/ranger/wiki/Integrating-File-Search-with-fzf
# Now, simply bind this function to a key, by adding this to your ~/.config/ranger/rc.conf: map <C-f> fzf_select
class fzf_select(Command):
    """
    :fzf_select

    Find a file using fzf.

    With a prefix argument select only directories.

    See: https://github.com/junegunn/fzf
    """
    def execute(self):
        wmroot, file_list = find_files(self.fm.start_paths[0], self.quantifier)

        fzf = self.fm.execute_command(
            'fzf +m',
            wait=False, # We're effectively waiting on the call to `communicate` below
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE)
        stdout, stderr = fzf.communicate(file_list)
        if fzf.returncode == 0:
            result = Path(stdout.decode('utf-8').rstrip())
            nav_path = Path(wmroot or '.').joinpath(result)
            fzf_file = os.path.abspath(nav_path.as_posix())
            if os.path.isdir(fzf_file):
                self.fm.cd(fzf_file)
            else:
                self.fm.select_file(fzf_file)

