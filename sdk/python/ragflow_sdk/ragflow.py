#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
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

from typing import Optional
import os

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from .modules.agent import Agent
from .modules.chat import Chat
from .modules.chunk import Chunk
from .modules.dataset import DataSet


class RAGFlow:
    def __init__(self, api_key, base_url, version="v1"):
        """
        api_url: http://<host_address>/api/v1
        """
        self.user_key = api_key
        self.api_url = f"{base_url}/api/{version}"
        self.authorization_header = {"Authorization": "{} {}".format("Bearer", self.user_key)}

    def post(self, path, json=None, stream=False, files=None):
        res = requests.post(url=self.api_url + path, json=json, headers=self.authorization_header, stream=stream, files=files)
        return res

    def get(self, path, params=None, json=None):
        res = requests.get(url=self.api_url + path, params=params, headers=self.authorization_header, json=json)
        return res

    def delete(self, path, json):
        res = requests.delete(url=self.api_url + path, json=json, headers=self.authorization_header)
        return res

    def put(self, path, json):
        res = requests.put(url=self.api_url + path, json=json, headers=self.authorization_header)
        return res

    def create_dataset(
        self,
        name: str,
        avatar: Optional[str] = None,
        description: Optional[str] = None,
        embedding_model: Optional[str] = None,
        permission: str = "me",
        chunk_method: str = "naive",
        parser_config: Optional[DataSet.ParserConfig] = None,
    ) -> DataSet:
        payload = {
            "name": name,
            "avatar": avatar,
            "description": description,
            "embedding_model": embedding_model,
            "permission": permission,
            "chunk_method": chunk_method,
        }
        if parser_config is not None:
            payload["parser_config"] = parser_config.to_json()

        res = self.post("/datasets", payload)
        res = res.json()
        if res.get("code") == 0:
            return DataSet(self, res["data"])
        raise Exception(res["message"])

    def delete_datasets(self, ids: list[str] | None = None):
        res = self.delete("/datasets", {"ids": ids})
        res = res.json()
        if res.get("code") != 0:
            raise Exception(res["message"])

    def get_dataset(self, name: str):
        _list = self.list_datasets(name=name)
        if len(_list) > 0:
            return _list[0]
        raise Exception("Dataset %s not found" % name)

    def list_datasets(self, page: int = 1, page_size: int = 30, orderby: str = "create_time", desc: bool = True, id: str | None = None, name: str | None = None) -> list[DataSet]:
        res = self.get(
            "/datasets",
            {
                "page": page,
                "page_size": page_size,
                "orderby": orderby,
                "desc": desc,
                "id": id,
                "name": name,
            },
        )
        res = res.json()
        result_list = []
        if res.get("code") == 0:
            for data in res["data"]:
                result_list.append(DataSet(self, data))
            return result_list
        raise Exception(res["message"])

    def create_chat(self, name: str, avatar: str = "", dataset_ids=None, llm: Chat.LLM | None = None, prompt: Chat.Prompt | None = None) -> Chat:
        if dataset_ids is None:
            dataset_ids = []
        dataset_list = []
        for id in dataset_ids:
            dataset_list.append(id)

        if llm is None:
            llm = Chat.LLM(
                self,
                {
                    "model_name": None,
                    "temperature": 0.1,
                    "top_p": 0.3,
                    "presence_penalty": 0.4,
                    "frequency_penalty": 0.7,
                    "max_tokens": 512,
                },
            )
        if prompt is None:
            prompt = Chat.Prompt(
                self,
                {
                    "similarity_threshold": 0.2,
                    "keywords_similarity_weight": 0.7,
                    "top_n": 8,
                    "top_k": 1024,
                    "variables": [{"key": "knowledge", "optional": True}],
                    "rerank_model": "",
                    "empty_response": None,
                    "opener": None,
                    "show_quote": True,
                    "prompt": None,
                },
            )
            if prompt.opener is None:
                prompt.opener = "Hi! I'm your assistant, what can I do for you?"
            if prompt.prompt is None:
                prompt.prompt = (
                    "You are an intelligent assistant. Please summarize the content of the knowledge base to answer the question. "
                    "Please list the data in the knowledge base and answer in detail. When all knowledge base content is irrelevant to the question, "
                    "your answer must include the sentence 'The answer you are looking for is not found in the knowledge base!' "
                    "Answers need to consider chat history.\nHere is the knowledge base:\n{knowledge}\nThe above is the knowledge base."
                )

        temp_dict = {"name": name, "avatar": avatar, "dataset_ids": dataset_list if dataset_list else [], "llm": llm.to_json(), "prompt": prompt.to_json()}
        res = self.post("/chats", temp_dict)
        res = res.json()
        if res.get("code") == 0:
            return Chat(self, res["data"])
        raise Exception(res["message"])

    def delete_chats(self, ids: list[str] | None = None):
        res = self.delete("/chats", {"ids": ids})
        res = res.json()
        if res.get("code") != 0:
            raise Exception(res["message"])

    def list_chats(self, page: int = 1, page_size: int = 30, orderby: str = "create_time", desc: bool = True, id: str | None = None, name: str | None = None) -> list[Chat]:
        res = self.get(
            "/chats",
            {
                "page": page,
                "page_size": page_size,
                "orderby": orderby,
                "desc": desc,
                "id": id,
                "name": name,
            },
        )
        res = res.json()
        result_list = []
        if res.get("code") == 0:
            for data in res["data"]:
                result_list.append(Chat(self, data))
            return result_list
        raise Exception(res["message"])

    def retrieve(
        self,
        dataset_ids,
        document_ids=None,
        question="",
        page=1,
        page_size=30,
        similarity_threshold=0.2,
        vector_similarity_weight=0.3,
        top_k=1024,
        rerank_id: str | None = None,
        keyword: bool = False,
    ):
        if document_ids is None:
            document_ids = []
        data_json = {
            "page": page,
            "page_size": page_size,
            "similarity_threshold": similarity_threshold,
            "vector_similarity_weight": vector_similarity_weight,
            "top_k": top_k,
            "rerank_id": rerank_id,
            "keyword": keyword,
            "question": question,
            "dataset_ids": dataset_ids,
            "document_ids": document_ids,
        }
        # Send a POST request to the backend service (using requests library as an example, actual implementation may vary)
        res = self.post("/retrieval", json=data_json)
        res = res.json()
        if res.get("code") == 0:
            chunks = []
            for chunk_data in res["data"].get("chunks"):
                chunk = Chunk(self, chunk_data)
                chunks.append(chunk)
            return chunks
        raise Exception(res.get("message"))

    def list_agents(self, page: int = 1, page_size: int = 30, orderby: str = "update_time", desc: bool = True, id: str | None = None, title: str | None = None) -> list[Agent]:
        res = self.get(
            "/agents",
            {
                "page": page,
                "page_size": page_size,
                "orderby": orderby,
                "desc": desc,
                "id": id,
                "title": title,
            },
        )
        res = res.json()
        result_list = []
        if res.get("code") == 0:
            for data in res["data"]:
                result_list.append(Agent(self, data))
            return result_list
        raise Exception(res["message"])

    def create_agent(self, title: str, dsl: dict, description: str | None = None) -> None:
        req = {"title": title, "dsl": dsl}

        if description is not None:
            req["description"] = description

        res = self.post("/agents", req)
        res = res.json()

        if res.get("code") != 0:
            raise Exception(res["message"])

    def update_agent(self, agent_id: str, title: str | None = None, description: str | None = None, dsl: dict | None = None) -> None:
        req = {}

        if title is not None:
            req["title"] = title

        if description is not None:
            req["description"] = description

        if dsl is not None:
            req["dsl"] = dsl

        res = self.put(f"/agents/{agent_id}", req)
        res = res.json()

        if res.get("code") != 0:
            raise Exception(res["message"])

    def delete_agent(self, agent_id: str) -> None:
        res = self.delete(f"/agents/{agent_id}", {})
        res = res.json()

        if res.get("code") != 0:
            raise Exception(res["message"])

    def upload_folder_to_dataset(self, folder_path: str, dataset_id: str, parent_id: str = ""):
        """
        Upload a folder and its contents to Ragflow, preserving directory structure,
        then convert files to documents and link them to the specified dataset.
        
        Args:
            folder_path: Local folder path to upload
            dataset_id: Target dataset ID to link documents
            parent_id: Parent folder ID in Ragflow (empty for root)
            
        Returns:
            dict: Upload result with file and document information
        """
        # Step 1: Upload files to file management system
        upload_result = self._upload_folder_preserve_structure(folder_path, parent_id)
        
        # Step 2: Get uploaded file IDs
        file_ids = [file_info["id"] for file_info in upload_result.get("data", [])]
        
        if not file_ids:
            return {"message": "No files uploaded", "data": []}
        
        # Step 3: Convert files to documents and link to dataset
        convert_result = self._convert_files_to_dataset(file_ids, [dataset_id])
        
        return {
            "message": "Successfully uploaded folder and linked to dataset",
            "upload_result": upload_result,
            "convert_result": convert_result
        }

    def _upload_folder_preserve_structure(self, folder_path: str, parent_id: str = ""):
        """
        Upload a folder preserving its directory structure using file upload API.
        """
        parts = []
        if parent_id:
            parts.append(('parent_id', parent_id))

        # Walk through the local folder
        for root, _, files in os.walk(folder_path):
            for filename in files:
                local_path = os.path.join(root, filename)
                # Calculate the relative path of the file
                relative_path = os.path.relpath(local_path, folder_path).replace('\\', '/')
                
                # Use the relative path as the filename in the multipart form
                parts.append(('file', (relative_path, open(local_path, 'rb'), 'application/octet-stream')))

        if len(parts) <= (1 if parent_id else 0):
            return {"message": "The folder is empty, no upload needed.", "data": []}

        encoder = MultipartEncoder(fields=parts)
        
        # Create headers for this specific request
        temp_headers = self.authorization_header.copy()
        temp_headers['Content-Type'] = encoder.content_type

        try:
            res = requests.post(
                url=self.api_url + "/file/upload",
                data=encoder,
                headers=temp_headers
            )
            res.raise_for_status()
            res_json = res.json()
            if res_json.get("code") != 0:
                raise Exception(res_json.get("message", "Upload failed"))
            return res_json
        finally:
            # Close all opened files
            for part in parts:
                if isinstance(part, tuple) and len(part) == 2 and isinstance(part[1], tuple):
                    if len(part[1]) >= 2 and hasattr(part[1][1], 'close'):
                        part[1][1].close()

    def _convert_files_to_dataset(self, file_ids: list[str], kb_ids: list[str]):
        """
        Convert uploaded files to documents and link them to datasets.
        Using the official API endpoint for better security and consistency.
        """
        payload = {
            "file_ids": file_ids,
            "kb_ids": kb_ids
        }
        
        res = self.post("/file2document/convert", payload)
        res_json = res.json()
        if res_json.get("code") != 0:
            raise Exception(res_json.get("message", "File to document conversion failed"))
        return res_json
    
    def upload_folder_to_dataset_direct(self, folder_path: str, dataset_id: str):
        """
        Alternative implementation: Upload files directly to dataset without using file management system.
        This bypasses the file management layer but is simpler and more direct.
        
        Args:
            folder_path: Local folder path to upload
            dataset_id: Target dataset ID
            
        Returns:
            list: List of created documents
        """
        import os
        
        # Get all files recursively
        file_list = []
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                file_list.append((abs_path, rel_path))
        
        # Prepare upload list for dataset.upload_documents
        upload_list = []
        for abs_path, rel_path in file_list:
            with open(abs_path, "rb") as f:
                blob = f.read()
            upload_list.append({
                "display_name": rel_path.replace("\\", "/"),  # Preserve directory structure in name
                "blob": blob
            })
        
        # Get dataset and upload
        dataset = self.get_dataset_by_id(dataset_id)
        return dataset.upload_documents(upload_list)
    
    def get_dataset_by_id(self, dataset_id: str):
        """
        Get dataset by ID
        """
        datasets = self.list_datasets()
        for dataset in datasets:
            if dataset.id == dataset_id:
                return dataset
        raise Exception(f"Dataset with ID {dataset_id} not found")
