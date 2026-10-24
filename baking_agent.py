from typing import List, Tuple, Dict, Any

from simulation_engine.gpt_structure import gpt_request_messages
from cs222_assignment_1_bonus.environment import BakingEnvironment

class Agent:
  def __init__(self, name: str, description: str):
    self.name, self.description = name, description
    self.message_history = []
    self.env = BakingEnvironment(self)

  def perceive(self) -> None:
    env_description = f"""
      Current baking environment:
      Available ingredients:
      {', '.join(self.env.ingredients.keys())}
      Ingredients added: 
      {', '.join(ing for ing, data in self.env.ingredients.items() if data['current'] > 0)}
      Available tools: 
      {', '.join(self.env.tools.keys())}
      Tools in use: 
      {', '.join(tool for tool, data in self.env.tools.items() if data['used'])}"""

    self.message_history.append({
      "role": "user",
      "content": env_description
    })

  def retrieve(self) -> str:
    """
    TODO
    In the agent's memories, there is a recipe for a cake buried amongst
    information about other topics. 

    Come up with a way to retrieve the relevant text from the agent's memory,
    without modifying the text file and minimizing the number of irrelevant
    information retrieved.

    Return the retrieved recipe (ingredients and steps) as a string.
    """
    
    memory_path = f"bonus/{self.name.lower()}/memory/cake.txt"
    with open(memory_path, "r", encoding="utf-8") as memory_file:
      memories = memory_file.read().split("\n\n")

    # The memory file contains unrelated articles as well as two recipe
    # paragraphs. Select those paragraphs by their explicit section headings
    # so the agent receives the recipe without the surrounding noise.
    recipe_sections = []
    for memory in memories:
      section = memory.strip()
      if section.lower().startswith("steps:") or section.lower().startswith("vanilla cake ingredients:"):
        recipe_sections.append(section)

    return "\n\n".join(recipe_sections)

  def act(self) -> str:
    persona = f"""
    You are {self.name}. {self.description} You are baking a cake right now.
    You remember the recipe for the cake:
    {self.retrieve()}

    Speak in character, no asterisks. Take only one action at a time.
    """

    response = gpt_request_messages(
      messages=[{"role": "system", "content": persona}] + self.message_history)
    return response


  def reflect(self, response: str) -> None:
    self.message_history.append({"role": "assistant", "content": response})


  def baking_step(self) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    self.perceive()
    action = self.act()
    self.reflect(action)
    attempted, executed, feedbacks = self.env.process_action(action)
    return action, attempted, executed, feedbacks
