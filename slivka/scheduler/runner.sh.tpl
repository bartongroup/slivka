#!/usr/bin/env sh
touch started
{cmd}
echo $? > finished
