#!/bin/sh
pylint -d missing-docstring -d line-too-long --reports=no --extension-pkg-whitelist=numpy *.py

