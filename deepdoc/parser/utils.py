#
#  Copyright 2025 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

from rag.nlp import find_codec


def get_text(fnm: str, binary=None) -> str:
    txt = ""
    if binary:
        encoding = find_codec(binary)
        txt = binary.decode(encoding, errors="ignore")
    else:
        # Only try to open file if it actually exists and binary is not available
        try:
            import os
            if os.path.exists(fnm):
                with open(fnm, "r") as f:
                    while True:
                        line = f.readline()
                        if not line:
                            break
                        txt += line
            else:
                # If file doesn't exist and no binary provided, raise a more informative error
                raise FileNotFoundError(f"File '{fnm}' not found and no binary data provided")
        except Exception as e:
            raise FileNotFoundError(f"Cannot read file '{fnm}': {e}")
    return txt
