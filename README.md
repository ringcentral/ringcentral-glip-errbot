# Errbot Glip Adapter

`ringcentral-glip-errbot` is an server backend adapter for [Errbot](http://errbot.io/) that allows you to use the robot with Glip.

## Installation

```bash
$ make install
```

## Configuration

Create `config.py` with the following info:

```python
BACKEND = 'Glip'

BOT_EXTRA_BACKEND_DIR = '/path_to/ringcentral-glip-errbot/src'

BOT_IDENTITY = {
    'username': '+11122233344',
    'extension': '',
    'password': 'FooBarBaz',
    'appKey': 'YourAppKey',
    'appSecret': 'YourAppSecret',
    'server': 'https://platform.ringcentral.com'
}
```

## Usage

```bash
$ make errbot
```
