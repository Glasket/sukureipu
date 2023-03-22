#!/usr/bin/env bash
cd "${0%/*}"
pyinstaller --clean -F -p "${PWD}" -p "${PWD}/util" sukureipu.py