#!/usr/bin/env bash
touch started
{cmd}
echo $? > finished
