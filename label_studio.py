from label_studio_sdk import LabelStudio
import json

LABEL_STUDIO_URL = "https://label-studio-814801174874.us-central1.run.app"
API_KEY = "<LEGACY_TOKEN>"

ls = LabelStudio(
    base_url=LABEL_STUDIO_URL, 
    api_key=API_KEY
)


# Define Label Config
# Remove Image section if needed
def generate_label_config(data: dict, num_turns: int) -> str:

    header = '''
<View className="root">
  <Style>
    .root {
      font-family: 'Roboto', sans-serif;
      background-color: #F9F9F9;
      line-height: 1.6;
    }
    .container {
      margin: 0 auto;
      padding: 20px;
      background-color: #fff;
      border-radius: 6px;
      box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    .turn {
      margin-bottom: 25px;
      padding: 15px;
      border: 1px solid #ddd;
      border-radius: 5px;
    }
    .user {
      background-color: #543ED4;
      color: #fff;
      padding: 10px;
      margin-bottom: 10px;
      border-radius: 5px;
    }
    .image {
      background-color: #FCE9CE;
      color: #000;
      padding: 10px;
      border-left: 4px solid #FF9F0D;
      margin-bottom: 10px;
      border-radius: 5px;
      font-family: monospace;
    }
    .image:hover {
      background-color: #F7DFB9;
      cursor: pointer;
      transition: 0.3s;
    }
    .assistant {
      background-color: #B96902;
      color: #fff;
      padding: 10px;
      border-radius: 5px;
      margin-bottom: 10px;
    }
    .assistant:hover {
      background-color: #C2740E;
      cursor: pointer;
      transition: 0.3s;
    }
  </Style>
  <View className="container">
'''

    body = ""
    for i in range(num_turns):
        if i == 0:
            body += f'''
    <View className="turn">
        <Collapse>
          <Panel value="Turn {i}">
            '''
        else:
            body += f'''
          </Panel>
          <Panel value="Turn {i}">
              '''
            
        body += f'''
          <View className="turn">
            <Header value="Turn {i}" size="4"/>
            <View className="user">
              <Header value="Math Question:"/>
              <TextArea name="user_{i}" toName="image_{i}" value="$turns.{i}.user" required="true" rows="4"  markdown="true"/>
            </View>
            <View className="image">
              <Header value="Generated Image"/>
              <Text name="image_{i}" value="$turns.{i}.image_url"/>
            </View>
            <View className="assistant">
              <Header value="Aymptote Code:"/>
              <TextArea name="assistant_{i}" toName="image_{i}" value="$turns.{i}.chat_text" required="true" rows="6" markdown="true"/>
              <Text name='asymptote_playground_{i}' value="Aymptote Playground: https://asymptote.ualberta.ca/"/>
            </View> 
          </View>
        '''
        if i == (num_turns-1):
            body += f'''
        </Panel>
      </Collapse>
    </View>
              '''

    footer = '''
  </View>
</View>'''
    return header + body + footer


# Import flattened dataset (type: json)
data_path = "data/turns_train.json"

with open(data_path, 'r') as file:
    data = json.load(file)
    
def normalize_chat_text(s: str) -> str:
    # Convert literal sequences to actual control chars
    s = s.replace("\\n", "\n").replace('\\"', '"')
    return s

for turn in data["turns"]:
    chat_text = turn.get("chat_text", "")
    chat_text = normalize_chat_text(chat_text)

    turn["chat_text"] = chat_text


# Create new LS project
LABEL_CONFIG = generate_label_config(data=data, num_turns=len(data["turns"]))

project = ls.projects.create(
        title="Asymptote Project",
        description=f"Cleaning Asymptote Dataset for Finetune Run",
        )

print(f"\nProject '{project.title}' created successfully with ID {project.id}")


# Import the conversation data as a task
ls.tasks.create(project=project.id, data=data)

print(f"\nTask successfully imported.")

project = ls.projects.update(id=project.id, label_config=LABEL_CONFIG)

print(f"\nConfig successfully updated.")