#!/usr/bin/env bash

rm -rf ./.ve

virtualenv --python `which python3` .ve

.ve/bin/pip install errbot
.ve/bin/pip install ringcentral

args=("$@")

if [ "${args[0]}" == "link" ]; then
    rm -rf ./.ve/lib/python3.6/site-packages/ringcentral
    ln -s "$PWD/../ringcentral-python/ringcentral" ./.ve/lib/python3.6/site-packages/ringcentral
fi