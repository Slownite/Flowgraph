from features import extract_features
from geometry import estimate_pose
from planner import plan


def preprocess(config):
    return config


def fallback(pose):
    return pose


def run_pipeline(config):
    image = preprocess(config)
    features = extract_features(image)
    pose = estimate_pose(features)
    if pose:
        return plan(pose)
    return fallback(pose)


def run_dynamic(callback, value):
    return callback(value)
