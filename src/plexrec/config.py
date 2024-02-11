import yaml

config = {}

with open("config.yml", encoding="utf-8") as f:
    config = yaml.load(f, yaml.Loader)
