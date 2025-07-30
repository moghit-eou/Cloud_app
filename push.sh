msg="$*"

echo "___________started__________"
git add .

echo "______________Committing $msg ______________"

git commit -m "$msg"

echo "______PUSHING______"
git push
EOF