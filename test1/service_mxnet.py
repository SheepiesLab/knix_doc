
import mxnet as mx
import json
import numpy as np
from mxnet.gluon.model_zoo import vision

ctx = mx.cpu()
resnet18 = vision.resnet18_v1(pretrained=True, ctx=ctx)
categories = np.array(json.load(open('image_net_labels.json', 'r')))


def service(req):
    filename = 'dog.jpg'
    image = mx.image.imread(filename)

    def transform(image):
        resized = mx.image.resize_short(image, 224)  # minimum 224x224 images
        cropped, crop_info = mx.image.center_crop(resized, (224, 224))
        normalized = mx.image.color_normalize(cropped.astype(np.float32)/255,
                                              mean=mx.nd.array(
                                                  [0.485, 0.456, 0.406]),
                                              std=mx.nd.array([0.229, 0.224, 0.225]))
        # the network expect batches of the form (N,3,224,224)
        # Transposing from (224, 224, 3) to (3, 224, 224)
        transposed = normalized.transpose((2, 0, 1))
        # change the shape from (3, 224, 224) to (1, 3, 224, 224)
        batchified = transposed.expand_dims(axis=0)
        return batchified

    def predict(model, image, categories, k):
        predictions = model(transform(image)).softmax()
        top_pred = predictions.topk(k=k)[0].asnumpy()
        catlist = {}
        for index in top_pred:
            probability = predictions[0][int(index)]
            category = categories[int(index)]
            catlist[category] = probability.asscalar()*100
            print("{}: {:.2f}%".format(category, probability.asscalar()*100))
        print('')
        return catlist

    catlist = predict(resnet18, image, categories, 3)

    return {'message': catlist, 'content': req}, 200
