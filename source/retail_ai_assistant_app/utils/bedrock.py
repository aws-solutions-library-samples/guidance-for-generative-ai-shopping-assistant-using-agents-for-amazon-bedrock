# utils/bedrock.py
import json
from botocore.exceptions import ClientError

class BedrockAgent:
    def __init__(self, _session, _logger):
        self.logger = _logger
        self.bedrock_agent_runtime = _session.client(
            service_name='bedrock-agent-runtime'
        )
        self.bedrock_runtime = _session.client(
            service_name='bedrock-runtime'
        )
        print("boto3 Bedrock Agent client successfully created!")
        print(self.bedrock_runtime._endpoint)
        
    
    def invoke_claude_model(self, prompt, base64_image= None, model_id='anthropic.claude-3-haiku-20240307-v1:0', generation_config = None):
        if prompt is None or prompt == '' or "claude" not in model_id:
            return

        try:
            outputText = ''

            accept = 'application/json'
            contentType = 'application/json'
            if generation_config is None:
                generation_config = {
                    "anthropic_version": "bedrock-2023-05-31",    
                    "max_tokens":4096,
                    "temperature":0,
                    "top_p":0.9
                }

            config = generation_config.copy()
            
            if base64_image:
                user_message = {"role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64",
                        "media_type": "image/jpeg", "data": base64_image}},
                    {"type": "text", "text": prompt}
                    ]}
            else:
                user_message =  {"role": "user", "content": prompt}
        
            messages = [user_message]

            config.update(
                    {"messages": messages}
                )
            
            body = json.dumps(config) 
            response = self.bedrock_runtime.invoke_model(body=body, modelId=model_id, accept=accept, contentType=contentType)
            response_body = json.loads(response.get('body').read())
            outputText = response_body["content"][0]["text"]

        except Exception as err:
            message = err.response["Error"]["Message"]
            self.logger.error("A client error occurred: %s", message)
            print("A client error occured: " +
                format(message))
        
        return outputText

    def invoke_agent(self, agent_id, agent_alias_id, session_id, session_state, prompt, base64_image = None, end_session:bool = False):
        try:
            if base64_image:
                output_text = self.invoke_claude_model("What's in my image", base64_image)
                if output_text:
                    prompt = prompt + "\n" + output_text
            
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime/client/invoke_agent.html
            response = self.bedrock_agent_runtime.invoke_agent(
                agentId=agent_id,
                agentAliasId=agent_alias_id,
                enableTrace=True,
                sessionId=session_id,
                inputText=prompt,
                sessionState= session_state,
                endSession = end_session
            )

            output_text = ""
            trace = {}

            event_stream = response.get("completion")
            try:
                for event in event_stream:        
                    if 'chunk' in event:
                        data = event['chunk']['bytes']
                        agent_answer = data.decode('utf8')
                        # Combine the chunks to get the output text
                        output_text += agent_answer
                        end_event_received = True
                        # End event indicates that the request finished successfully
                    elif 'trace' in event:
                            # Extract trace information from all events
                        for trace_type in ["preProcessingTrace", "orchestrationTrace", "postProcessingTrace"]:
                            #print(event)
                            if trace_type in event["trace"]["trace"]:
                                if trace_type not in trace:
                                    trace[trace_type] = []
                                trace[trace_type].append(event["trace"]["trace"][trace_type])
                    else:
                        raise Exception("unexpected event.", event)
            except Exception as e:
                raise Exception("unexpected event.", e)
        except ClientError as e:
            raise

        return {
            "output_text": output_text,
            "trace": trace
        }


