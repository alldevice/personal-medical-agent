# Recommended server layout

```text
/srv/hermes-medical/
  repo/       # git clone, owner hermes:hermes, mode 750
  data/       # real medical vault, owner hermes:hermes, mode 700
  config/     # local .env/settings, owner hermes:hermes, mode 700
```

Use `aiadmin`/root for setup and `hermes` for ownership/runtime.

```bash
sudo install -d -m 755 -o root -g root /srv/hermes-medical
sudo install -d -m 750 -o hermes -g hermes /srv/hermes-medical/repo
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/data
sudo install -d -m 700 -o hermes -g hermes /srv/hermes-medical/config
```

Do not add `hermes` to the Docker group for this MVP.
