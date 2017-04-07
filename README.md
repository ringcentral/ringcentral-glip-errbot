# Errbot Glip Adapter

`ringcentral-glip-errbot` is an server backend adapter for [Errbot](http://errbot.io/) that allows you to use the robot with Glip.

## Installation

```bash
$ make install
```

## Configuration

Run the bot with text backend and do:

```
!plugin config Webserver {'HOST': '0.0.0.0', 'PORT': 3141}
```

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
    'server': 'https://platform.ringcentral.com',
    'webhookServer': 'https://demo.ngrok.io:8888'  # Your Errbot port
}
```

## Usage

```bash
$ make errbot
```
