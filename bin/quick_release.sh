#!/bin/bash -xeu

version=$(($(git tag | sort -n | tail -n1)+1))
echo "will perform quick release $version"
# TODO passing a tag message to git flow does not work right now
#message=$(mktemp /tmp/gitflowreleasemessage.XXXX)
#echo "tagged version $version" > $message
git flow release start $version
git flow release finish $version # -f $message
git push origin master
git push origin develop
git push origin $version
git checkout develop
