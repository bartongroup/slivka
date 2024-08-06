#!/usr/bin/env bash
touch started
{cmd} >stdout
echo $? > finished

