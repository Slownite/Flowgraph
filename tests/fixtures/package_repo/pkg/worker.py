import json


class Runner:
    def run(self):
        return self.step()

    def step(self):
        return json.dumps({"done": True})


def execute():
    return Runner.run()
