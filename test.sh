#!/bin/bash

BACKUP_FILE="/path/to/db.sqlite3"
BACKUP_DIR="$HOME/backups"

today=`date "+%Y-%m-%d"`

# Less than 31 days old, i.e. 30 days or younger
if find "$BACKUP_FILE" -type f -mtime -31 | grep -q .
then
        find "$BACKUP_DIR" -type f -mtime +30 -exec rm {} \;
fi

last_backup=$(ls -t "$BACKUP_DIR" | head -1)
if [ -n "$last_backup" ] && diff "$BACKUP_FILE" "$BACKUP_DIR/$(ls -t "$BACKUP_DIR" | head -1)" >/dev/null
then :
else
        cp "$BACKUP_FILE" "$BACKUP_DIR/$today.sqlite3"
fi