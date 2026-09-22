class Location:
    def __init__(self, dimension, x, y, z, pitch=0.0, yaw=0.0):
        self.dimension = dimension
        self.x, self.y, self.z = x, y, z
        self.pitch, self.yaw = pitch, yaw
