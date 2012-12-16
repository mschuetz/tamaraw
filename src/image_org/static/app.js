$(function() {

_.mixin({
	partition: function (arr, size){
	    if (_.size(arr) <= size) {
	    	return [arr];
	    }
	    return [_.first(arr, size)].concat(_.partition(_.rest(arr,size), size));
	}
});
	
window.Image = Backbone.Model.extend();

window.ImageCollection = Backbone.Collection.extend({
	model: Image,
	url: '/images'
});

window.ImageListView = Backbone.View.extend({
	tagName: 'div',
	initialize: function() {
		this.model.bind("reset", this.render, this);
	},
	render: function(eventName) {
		_.each(_.partition(this.model.models, 4), function(images) {
			listElement = $('<ul class="thumbnails"></ul>').appendTo(this.$el)
			_.each(images, function(image) {
				listElement.append(new ImageListItemView({model: image }).render().el);
			}, this);
		}, this);
		return this;
	}
});

window.ImageListItemView = Backbone.View.extend({
	tagName: 'li',
	className: 'span3',
	initialize: function(){
		this.model.bind("reset", this.render, this);
	},
	template: _.template($('#tpl-image-list-item').html()),
	render: function(eventName) {
		this.$el.html(this.template(this.model.toJSON()));
		return this;
	}
});

var AppRouter = Backbone.Router.extend({
	routes: {
		"": "list"
	},
	list: function(){
		this.imageList = new ImageCollection();
		this.imageListView = new ImageListView({model: this.imageList});
		this.imageList.fetch();
		$('#content').html(this.imageListView.render().el);
	}
});

var app = new AppRouter();
Backbone.history.start();
});
