#!/bin/sh

ARGS_NR=$#

ACTIONS=$(find . | xargs | sed 's/\.\/foxpass_//gi' | sed 's/\.py//gi' | sed 's/\. //gi' | sed 's/\.\/api\.sh //gi')

if [ $ARGS_NR -lt 1 ]; then
  >&2 echo "ERROR: Invalid number of arguments."
  >&2 echo "  Usage:"
  >&2 echo "    docker run foxpass <action> [<options>]" 
  >&2 echo "  Actions: $ACTIONS"
  >&2 echo "  Examples:"
  >&2 echo "    docker run foxpass copy_group [<options>]" 
  >&2 echo "    docker run foxpass deactivate_user [<options>]" 

  exit 1
fi

ACTION=$1
COMMAND="$(pwd)/foxpass_$ACTION.py"
shift
OPTIONS=$@

if [ ! -f $COMMAND ]; then
  >&2 echo "ERROR: Action '$ACTION' does not exists."
  >&2 echo "  Possible actions: $ACTIONS"
  exit 1
fi

python "$COMMAND" $OPTIONS
