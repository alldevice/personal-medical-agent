# Recommended server layout

```text
/srv/hermes-medical/
  repo/       # git clone
  data/       # real vault, chmod 700
  config/     # .env, chmod 700, files chmod 600
```

Initial commands:

```bash
sudo mkdir -p /srv/hermes-medical/{repo,data,config}
sudo chown -R hermes:hermes /srv/hermes-medical
chmod 700 /srv/hermes-medical/data /srv/hermes-medical/config
```
