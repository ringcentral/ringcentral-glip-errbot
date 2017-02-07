.PHONY: intall
intall:
	./install.sh

.PHONY: errbot
errbot:
	.ve/bin/errbot

.PHONY: ngrok
ngrok:
	ngrok http 3141