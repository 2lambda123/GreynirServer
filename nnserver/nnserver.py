#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    Reynir: Natural language processing for Icelandic

    Neural Network Query Client

    Copyright (C) 2018 Miðeind

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module implements a server that provides an icelandic text interface to
    an NMT parsing tensorflow model server.

"""

import base64
import json
import requests

from composite_encoder import CompositeTokenEncoder as ParsingEncoder

from tensor2tensor.data_generators import text_encoder
from tensorflow.core.example import feature_pb2
from tensorflow.core.example import example_pb2

from flask import Flask, jsonify, request


EOS_ID = text_encoder.EOS_ID
PAD_ID = text_encoder.PAD_ID

_PARSING_VOCAB_PATH = "../resources/parsing_tokens_180729.txt"
_ENIS_VOCAB_PATH = "../resources/vocab.enis.16384.subwords"


app = Flask(__name__)


class NnServer:
    """ Client that minics the HTTP RESTful interface of
        a tensorflow model server, but accepts plain text. """

    host = app.config.get("host")
    port = app.config.get("port")
    _tfms_version = "v1"
    _model_name = "transformer"
    _verb = "predict"
    _parsingEncoder = ParsingEncoder(_PARSING_VOCAB_PATH, version=2)
    _enisEncoder = text_encoder.SubwordTextEncoder(_ENIS_VOCAB_PATH)

    @classmethod
    def request(cls, pgs):
        """ Send serialized request to remote model server """
        url = "http://{host}:{port}/{version}/models/{model}:{verb}".format(
            port=cls.port,
            host=cls.host,
            version=cls._tfms_version,
            model=cls._model_name,
            verb=cls._verb,
        )
        headers = {"content-type": "application/json"}
        instances = [cls.serialize_to_instance(sent) for sent in pgs]

        payload = {
            "signature_name": "serving_default",
            "instances": [inst for inst in instances],
        }
        payload = json.dumps(payload)
        resp = requests.post(url, data=payload, headers=headers)

        try:
            obj = json.loads(resp.text)
            predictions = obj["predictions"]
            results = [
                cls.process_response_instance(inst, sent)
                for (inst, sent) in zip(predictions, pgs)
            ]
            # return results
            obj["predictions"] = results
            return obj
        except Exception as e:
            print(e)
            return None

    @classmethod
    def process_response_instance(cls, instance, sent):
        """  Process the numerical output from the model server for one sentence """
        scores = instance["scores"]
        output_ids = instance["outputs"]

        # Strip padding and eos token
        length = len(output_ids)
        pad_start = output_ids.index(PAD_ID) if PAD_ID in output_ids else length
        eos_start = output_ids.index(EOS_ID) if EOS_ID in output_ids else length
        sent_end = min(pad_start, eos_start)
        output_toks = cls._parsingEncoder.decode(output_ids[:sent_end])
        instance["outputs"] = output_toks

        # return output_toks
        return instance

    @classmethod
    def serialize_to_instance(cls, sent):
        """ Encodes a single sentence into the format expected by the RESTful interface
        of tensorflow_model_server running an exported tensor2tensor transformer translation model """
        # Add end of sentence token
        input_ids = cls._enisEncoder.encode(sent)
        input_ids.extend([EOS_ID])

        int64_list = feature_pb2.Int64List(value=input_ids)
        feature = feature_pb2.Feature(int64_list=int64_list)
        feature_map = {"inputs": feature}
        features = feature_pb2.Features(feature=feature_map)
        example = example_pb2.Example(features=features)

        b64_example = base64.b64encode(example.SerializeToString()).decode("utf-8")
        return {"input": {"b64": b64_example}}


@app.route("/parse.api", methods=["POST"])
def test():
    try:
        req_body = request.data.decode("utf-8")
        obj = json.loads(req_body)
        # TODO: validate form?
        pgs = obj["pgs"]
        model_response = NnServer.request(pgs)
        resp = jsonify(model_response)
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp
    except:
        resp = jsonify(valid=False, reason="Invalid request")
        resp.headers["Content-Type"] = "application/json; charset=utf-8"
        return resp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Middleware server for providing a textual interface to tensorflow model server"
        )
    )
    parser.add_argument(
        "--listen_host",
        dest="IN_HOST",
        required=False,
        type=str,
        default="localhost",
        help="Hostname to listen on",
    )
    parser.add_argument(
        "--listen_port",
        dest="IN_PORT",
        required=False,
        type=str,
        default="8080"
        help="Port to listen on",
    )
    parser.add_argument(
        "--model_host",
        dest="OUT_HOST",
        required=False,
        type=str,
        default="localhost",
        help="Hostname of model server",
    )
    parser.add_argument(
        "--model_port",
        dest="9000",
        required=False,
        type=str,
        help="Port of model server",
    )

    args = parser.parse_args()
    app.config["out_host"] = args.OUT_HOST
    app.config["out_port"] = args.OUT_PORT
    app.run(debug=True, host=args.IN_HOST, port=args.IN_PORT)