from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import anthropic


class ConversationState(Enum):
    INITIAL = "initial"
    TOOL_EXECUTING = "tool_executing"
    AWAITING_FOLLOWUP = "awaiting_followup"
    COMPLETE = "complete"


@dataclass
class ConversationContext:
    messages: List[Dict[str, Any]] = field(default_factory=list)
    state: ConversationState = ConversationState.INITIAL
    round_number: int = 0
    max_rounds: int = 2
    system_content: str = ""
    tool_execution_errors: List[str] = field(default_factory=list)
    rollback_point: Optional[Dict[str, Any]] = None


class StateTransitionManager:
    @staticmethod
    def can_transition(
        current_state: ConversationState, new_state: ConversationState
    ) -> bool:
        valid_transitions = {
            ConversationState.INITIAL: [
                ConversationState.TOOL_EXECUTING,
                ConversationState.COMPLETE,
            ],
            ConversationState.TOOL_EXECUTING: [
                ConversationState.AWAITING_FOLLOWUP,
                ConversationState.COMPLETE,
            ],
            ConversationState.AWAITING_FOLLOWUP: [
                ConversationState.TOOL_EXECUTING,
                ConversationState.COMPLETE,
            ],
            ConversationState.COMPLETE: [],
        }
        return new_state in valid_transitions.get(current_state, [])

    @staticmethod
    def transition(context: ConversationContext, new_state: ConversationState) -> bool:
        if StateTransitionManager.can_transition(context.state, new_state):
            context.state = new_state
            return True
        return False


class ConversationBuilder:
    def __init__(self, ai_generator):
        self.ai_generator = ai_generator

    def build_system_prompt(self, context: ConversationContext) -> str:
        # Use the context's system_content if it includes conversation history
        base_prompt = (
            context.system_content
            if context.system_content
            else self.ai_generator.SYSTEM_PROMPT
        )

        if context.state == ConversationState.INITIAL:
            return base_prompt
        elif context.state == ConversationState.AWAITING_FOLLOWUP:
            return (
                base_prompt
                + """

You are now in a follow-up round. You have access to previous tool results and can make additional tool calls to:
- Compare information across different sources
- Search for additional details based on previous results
- Synthesize information from multiple searches

Consider the previous tool results and determine if you need more information to provide a complete answer."""
            )
        else:
            return base_prompt

    def create_rollback_point(self, context: ConversationContext):
        context.rollback_point = {
            "messages": context.messages.copy(),
            "round_number": context.round_number,
            "state": context.state,
        }

    def rollback(self, context: ConversationContext) -> bool:
        if context.rollback_point:
            context.messages = context.rollback_point["messages"]
            context.round_number = context.rollback_point["round_number"]
            context.state = context.rollback_point["state"]
            context.rollback_point = None
            return True
        return False


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """You are an AI assistant with access to exactly two tools. You can make multiple tool calls across up to 2 rounds to gather complete information. Follow these rules EXACTLY:

TOOL SELECTION EXAMPLES:
- "What lessons are in MCP course?" → USE get_course_outline
- "Show MCP course outline" → USE get_course_outline  
- "List all lessons in course X" → USE get_course_outline
- "Course structure for X" → USE get_course_outline
- "What's covered in course X" → USE get_course_outline

- "What does lesson 5 cover?" → USE search_course_content
- "Explain MCP architecture from lesson 2" → USE search_course_content

MANDATORY RULES:
1. For ANY query asking about lesson lists, course structure, outlines, or "what lessons" → USE get_course_outline
2. For specific lesson content → USE search_course_content
3. When you use get_course_outline, present the EXACT results returned - never modify or add "[not available]"

MULTI-ROUND TOOL CALLING:
You can make sequential tool calls across multiple rounds. Use this for:
- Comparing information across courses/lessons
- Getting course outline first, then searching specific lesson content
- Gathering multiple pieces of information to provide comprehensive answers

EXAMPLES OF MULTI-ROUND QUERIES:
- "Search for a course that discusses the same topic as lesson 4 of course X" → Round 1: get_course_outline for course X to find lesson 4 topic, Round 2: search for courses with that topic
- "Compare lesson 3 of course A with lesson 5 of course B" → Round 1: search lesson 3 content, Round 2: search lesson 5 content
- "What courses cover similar topics to the introduction lesson of course X?" → Round 1: get course outline for course X, Round 2: search for courses with similar intro topics

The get_course_outline tool returns complete course information with all lesson titles. Trust its results completely.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.conversation_builder = ConversationBuilder(self)

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context using state machine.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """
        # Initialize conversation context
        context = ConversationContext()
        context.messages = [{"role": "user", "content": query}]
        context.system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Use state machine to handle the conversation
        return self._handle_sequential_conversation(context, tools, tool_manager)

    def _handle_sequential_conversation(
        self,
        context: ConversationContext,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Handle sequential conversation using state machine pattern.

        Args:
            context: Current conversation context with state and messages
            tools: Available tools for AI to use
            tool_manager: Manager to execute tools

        Returns:
            Final response text after all rounds
        """
        while (
            context.state != ConversationState.COMPLETE
            and context.round_number < context.max_rounds
        ):
            try:
                # Create rollback point before each round
                self.conversation_builder.create_rollback_point(context)

                # Make API call for current round
                response = self._make_api_call(context, tools)

                # Check if response contains tool use
                has_tool_use = any(
                    block.type == "tool_use" for block in response.content
                )

                if has_tool_use and tool_manager:
                    # Transition to tool executing state
                    StateTransitionManager.transition(
                        context, ConversationState.TOOL_EXECUTING
                    )

                    # Add assistant response to conversation
                    context.messages.append(
                        {"role": "assistant", "content": response.content}
                    )

                    # Execute tools and add results
                    if self._execute_tools_for_round(response, context, tool_manager):
                        # Increment round and transition to awaiting followup
                        context.round_number += 1
                        if context.round_number < context.max_rounds:
                            StateTransitionManager.transition(
                                context, ConversationState.AWAITING_FOLLOWUP
                            )
                        else:
                            # Final round - make one more call to get synthesis
                            final_response = self._make_final_api_call(context)
                            StateTransitionManager.transition(
                                context, ConversationState.COMPLETE
                            )
                            return final_response.content[0].text
                    else:
                        # Tool execution failed, rollback and return error
                        self.conversation_builder.rollback(context)
                        return "I encountered an error while processing your request. Please try again."
                else:
                    # No tool use - this is the final response
                    StateTransitionManager.transition(
                        context, ConversationState.COMPLETE
                    )
                    return response.content[0].text

            except Exception as e:
                # Handle API or other errors
                context.tool_execution_errors.append(str(e))
                if self.conversation_builder.rollback(context):
                    return "I encountered an error while processing your request. Please try again."
                else:
                    return f"An error occurred: {str(e)}"

        # If we've completed max rounds, make final synthesis call
        if context.state != ConversationState.COMPLETE:
            try:
                final_response = self._make_final_api_call(context)
                return final_response.content[0].text
            except Exception:
                return "I've gathered information but encountered an error in the final response. Please try again."

        return "No response generated."

    def _make_api_call(
        self, context: ConversationContext, tools: Optional[List] = None
    ):
        """Make API call to Claude with current conversation state."""
        # Build system prompt based on current state
        system_prompt = self.conversation_builder.build_system_prompt(context)

        # Prepare API parameters
        api_params = {
            **self.base_params,
            "messages": context.messages.copy(),
            "system": system_prompt,
        }

        # Add tools if available and not in final state
        if tools and context.state != ConversationState.COMPLETE:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        return self.client.messages.create(**api_params)

    def _make_final_api_call(self, context: ConversationContext):
        """Make final API call without tools for synthesis."""
        api_params = {
            **self.base_params,
            "messages": context.messages.copy(),
            "system": context.system_content,
        }
        return self.client.messages.create(**api_params)

    def _execute_tools_for_round(
        self, response, context: ConversationContext, tool_manager
    ) -> bool:
        """Execute all tool calls for current round and add results to context."""
        tool_results = []

        try:
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_result = tool_manager.execute_tool(
                        content_block.name, **content_block.input
                    )

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )

            # Add tool results to conversation
            if tool_results:
                context.messages.append({"role": "user", "content": tool_results})

            return True

        except Exception as e:
            context.tool_execution_errors.append(str(e))
            return False
