import pytest
from unittest.mock import Mock, MagicMock, call
import anthropic
from ai_generator import AIGenerator, ConversationState, ConversationContext, StateTransitionManager, ConversationBuilder


class MockClient:
    def __init__(self):
        self.messages = Mock()
        self.create_response_history = []

    def create_mock_response(self, content, stop_reason="end_turn", tool_calls=None):
        response = Mock()
        response.content = []
        
        if isinstance(content, str):
            text_block = Mock()
            text_block.type = "text"
            text_block.text = content
            response.content = [text_block]
        else:
            # Handle tool use content blocks
            for block in content:
                mock_block = Mock()
                mock_block.type = block.get("type", "text")
                if block["type"] == "tool_use":
                    mock_block.name = block["name"]
                    mock_block.input = block["input"]
                    mock_block.id = block.get("id", "tool_123")
                else:
                    mock_block.text = block.get("text", "")
                response.content.append(mock_block)
        
        response.stop_reason = stop_reason
        return response


class MockToolManager:
    def __init__(self):
        self.executed_tools = []
    
    def execute_tool(self, name, **kwargs):
        self.executed_tools.append({"name": name, "args": kwargs})
        if name == "get_course_outline":
            return "Course X: Lesson 1: Intro, Lesson 2: Advanced Topics"
        elif name == "search_course_content":
            return "Lesson content about specific topic"
        return "Mock tool result"


@pytest.fixture
def mock_anthropic_client():
    mock_client = MockClient()
    return mock_client


@pytest.fixture
def ai_generator(mock_anthropic_client):
    generator = AIGenerator("test_api_key", "claude-3-sonnet")
    generator.client = mock_anthropic_client
    return generator


@pytest.fixture
def mock_tool_manager():
    return MockToolManager()


@pytest.fixture
def sample_tools():
    return [
        {
            "name": "get_course_outline",
            "description": "Get course outline",
            "input_schema": {"type": "object", "properties": {}}
        },
        {
            "name": "search_course_content", 
            "description": "Search course content",
            "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}
        }
    ]


class TestConversationState:
    def test_state_enum_values(self):
        assert ConversationState.INITIAL.value == "initial"
        assert ConversationState.TOOL_EXECUTING.value == "tool_executing"
        assert ConversationState.AWAITING_FOLLOWUP.value == "awaiting_followup"
        assert ConversationState.COMPLETE.value == "complete"


class TestStateTransitionManager:
    def test_valid_transitions_from_initial(self):
        assert StateTransitionManager.can_transition(
            ConversationState.INITIAL, ConversationState.TOOL_EXECUTING
        )
        assert StateTransitionManager.can_transition(
            ConversationState.INITIAL, ConversationState.COMPLETE
        )
        assert not StateTransitionManager.can_transition(
            ConversationState.INITIAL, ConversationState.AWAITING_FOLLOWUP
        )
    
    def test_valid_transitions_from_tool_executing(self):
        assert StateTransitionManager.can_transition(
            ConversationState.TOOL_EXECUTING, ConversationState.AWAITING_FOLLOWUP
        )
        assert StateTransitionManager.can_transition(
            ConversationState.TOOL_EXECUTING, ConversationState.COMPLETE
        )
    
    def test_transition_updates_context_state(self):
        context = ConversationContext()
        initial_state = context.state
        
        success = StateTransitionManager.transition(context, ConversationState.TOOL_EXECUTING)
        
        assert success
        assert context.state == ConversationState.TOOL_EXECUTING
        assert context.state != initial_state


class TestConversationBuilder:
    def test_build_system_prompt_initial_state(self, ai_generator):
        builder = ConversationBuilder(ai_generator)
        context = ConversationContext()
        
        prompt = builder.build_system_prompt(context)
        
        assert ai_generator.SYSTEM_PROMPT in prompt
        assert "follow-up round" not in prompt.lower()
    
    def test_build_system_prompt_followup_state(self, ai_generator):
        builder = ConversationBuilder(ai_generator)
        context = ConversationContext()
        context.state = ConversationState.AWAITING_FOLLOWUP
        
        prompt = builder.build_system_prompt(context)
        
        assert ai_generator.SYSTEM_PROMPT in prompt
        assert "follow-up round" in prompt.lower()
    
    def test_rollback_functionality(self, ai_generator):
        builder = ConversationBuilder(ai_generator)
        context = ConversationContext()
        context.messages = [{"role": "user", "content": "original"}]
        context.round_number = 0
        
        # Create rollback point
        builder.create_rollback_point(context)
        
        # Modify context
        context.messages.append({"role": "assistant", "content": "modified"})
        context.round_number = 1
        
        # Rollback
        success = builder.rollback(context)
        
        assert success
        assert len(context.messages) == 1
        assert context.messages[0]["content"] == "original"
        assert context.round_number == 0


class TestAIGenerator:
    def test_single_round_no_tools(self, ai_generator, mock_anthropic_client):
        # Setup mock response
        mock_response = mock_anthropic_client.create_mock_response("Simple response")
        mock_anthropic_client.messages.create = Mock(return_value=mock_response)
        
        result = ai_generator.generate_response("Test query")
        
        assert result == "Simple response"
        mock_anthropic_client.messages.create.assert_called_once()
        
        # Verify API parameters
        call_args = mock_anthropic_client.messages.create.call_args
        assert "tools" not in call_args[1]
    
    def test_single_round_with_tool_call(self, ai_generator, mock_anthropic_client, mock_tool_manager, sample_tools):
        # Setup mock responses
        tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        final_response = mock_anthropic_client.create_mock_response("Final response with tool result")
        
        mock_anthropic_client.messages.create = Mock(side_effect=[tool_response, final_response])
        
        result = ai_generator.generate_response(
            "What lessons are in the course?",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        assert result == "Final response with tool result"
        assert len(mock_tool_manager.executed_tools) == 1
        assert mock_tool_manager.executed_tools[0]["name"] == "get_course_outline"
        
        # Verify two API calls were made
        assert mock_anthropic_client.messages.create.call_count == 2
    
    def test_two_round_tool_calling(self, ai_generator, mock_anthropic_client, mock_tool_manager, sample_tools):
        # Setup mock responses for two rounds of tool calling
        first_tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {"course": "X"}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        second_tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "search_course_content", "input": {"query": "lesson 1"}, "id": "tool_456"}
        ], stop_reason="tool_use")
        
        final_response = mock_anthropic_client.create_mock_response("Comprehensive answer using both tool results")
        
        mock_anthropic_client.messages.create = Mock(
            side_effect=[first_tool_response, second_tool_response, final_response]
        )
        
        result = ai_generator.generate_response(
            "Compare lesson 1 topics across courses",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        assert result == "Comprehensive answer using both tool results"
        assert len(mock_tool_manager.executed_tools) == 2
        assert mock_tool_manager.executed_tools[0]["name"] == "get_course_outline"
        assert mock_tool_manager.executed_tools[1]["name"] == "search_course_content"
        
        # Verify three API calls were made (2 tool rounds + 1 final)
        assert mock_anthropic_client.messages.create.call_count == 3
    
    def test_max_rounds_limit(self, ai_generator, mock_anthropic_client, mock_tool_manager, sample_tools):
        # Setup mock to return tool use responses indefinitely
        tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        final_response = mock_anthropic_client.create_mock_response("Final synthesis response")
        
        # Return tool responses for first 2 calls, then final response
        mock_anthropic_client.messages.create = Mock(
            side_effect=[tool_response, tool_response, final_response]
        )
        
        result = ai_generator.generate_response(
            "Complex multi-step query",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        assert result == "Final synthesis response"
        # Should stop after 2 tool rounds
        assert len(mock_tool_manager.executed_tools) == 2
        assert mock_anthropic_client.messages.create.call_count == 3
    
    def test_tool_execution_error_handling(self, ai_generator, mock_anthropic_client, sample_tools):
        # Setup tool manager that raises an exception
        failing_tool_manager = Mock()
        failing_tool_manager.execute_tool = Mock(side_effect=Exception("Tool execution failed"))
        
        tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        mock_anthropic_client.messages.create = Mock(return_value=tool_response)
        
        result = ai_generator.generate_response(
            "Test query",
            tools=sample_tools,
            tool_manager=failing_tool_manager
        )
        
        assert "error" in result.lower()
        assert mock_anthropic_client.messages.create.call_count == 1
    
    def test_conversation_history_preservation(self, ai_generator, mock_anthropic_client, mock_tool_manager, sample_tools):
        # Test that conversation history is maintained across rounds
        first_tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        final_response = mock_anthropic_client.create_mock_response("Response with history")
        
        mock_anthropic_client.messages.create = Mock(side_effect=[first_tool_response, final_response])
        
        result = ai_generator.generate_response(
            "Test query",
            conversation_history="Previous: User asked about courses",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Verify conversation history was included in system prompt
        first_call_args = mock_anthropic_client.messages.create.call_args_list[0][1]
        assert "Previous: User asked about courses" in first_call_args["system"]
    
    def test_system_prompt_changes_between_rounds(self, ai_generator, mock_anthropic_client, mock_tool_manager, sample_tools):
        # Test that system prompt is enhanced for follow-up rounds
        first_tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "get_course_outline", "input": {}, "id": "tool_123"}
        ], stop_reason="tool_use")
        
        second_tool_response = mock_anthropic_client.create_mock_response([
            {"type": "tool_use", "name": "search_course_content", "input": {"query": "test"}, "id": "tool_456"}  
        ], stop_reason="tool_use")
        
        final_response = mock_anthropic_client.create_mock_response("Final response")
        
        mock_anthropic_client.messages.create = Mock(
            side_effect=[first_tool_response, second_tool_response, final_response]
        )
        
        ai_generator.generate_response(
            "Multi-round query",
            tools=sample_tools,
            tool_manager=mock_tool_manager
        )
        
        # Check that second round has enhanced system prompt
        call_args_list = mock_anthropic_client.messages.create.call_args_list
        first_system = call_args_list[0][1]["system"]
        second_system = call_args_list[1][1]["system"]
        
        assert "follow-up round" not in first_system.lower()
        assert "follow-up round" in second_system.lower()


if __name__ == "__main__":
    pytest.main([__file__])