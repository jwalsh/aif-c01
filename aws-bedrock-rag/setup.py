!pip install anthropic
!pip install voyageai
!pip install pandas
!pip install numpy
!pip install matplotlib
!pip install seaborn
!pip install -U scikit-learn

import os
os.environ['VOYAGE_API_KEY'] = "VOYAGE KEY HERE"
os.environ['ANTHROPIC_API_KEY'] = "ANTHROPIC KEY HERE"

import anthropic
import os
client = anthropic.Anthropic(
    # This is the default and can be omitted
    api_key=os.getenv("ANTHROPIC_API_KEY"),)
