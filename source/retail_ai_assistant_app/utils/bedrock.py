# utils/bedrock.py

import boto3
import streamlit as st
from botocore.exceptions import ClientError

class BedrockAgent:
    def __init__(self, _session, _logger):
        self.logger = _logger
        self.bedrock_runtime = _session.client(
            service_name='bedrock-agent-runtime'
        )
        print("boto3 Bedrock Agent client successfully created!")
        print(self.bedrock_runtime._endpoint)

    def invoke_agent(self, agent_id, agent_alias_id, session_id, session_state, prompt, end_session:bool = False):
        try:

            # self.logger.info(f'Request params:',agent_id, agent_alias_id, session_id, prompt, end_session)
            
            # See https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-agent-runtime/client/invoke_agent.html
            response = self.bedrock_runtime.invoke_agent(
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


