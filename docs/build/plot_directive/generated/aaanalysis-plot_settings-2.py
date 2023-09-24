import matplotlib.pyplot as plt
import seaborn as sns
import aaanalysis as aa
data = {'Classes': ['Class A', 'Class B', 'Class C'], 'Values': [23, 27, 43]}
colors = aa.plot_get_cmap(name="TAB", n_colors=3)
sns.barplot(x='Classes', y='Values', data=data, palette=colors)
sns.despine()
plt.title("Seaborn default")
plt.tight_layout()
plt.show()
