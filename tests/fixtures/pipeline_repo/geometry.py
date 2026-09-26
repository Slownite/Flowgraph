def build_correspondences(features):
    return features


def compute_transform(correspondences):
    return correspondences


def validate_pose(transform):
    return bool(transform)


def estimate_pose(features):
    correspondences = build_correspondences(features)
    transform = compute_transform(correspondences)
    return transform if validate_pose(transform) else None
