msg="$*"

echo "git add started"
git add .

echo "Committing $msg"

git commit -m "$msg"

echo "PUSH"
git push
EOF