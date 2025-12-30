# Exempel på UFW-brandväggsregler för EC2
# Kör som root på servern
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
ufw status
